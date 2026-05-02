from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import typer
from sqlalchemy import select, text

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction
from app.models.user import User
from app.models.valuation import Valuation
from app.models.mis import MisBuMonthly, MisMonthly, MisSubmission
from app.schemas.transaction import NEGATIVE_TYPES, POSITIVE_TYPES
from app.services import metrics_service
from app.services.sample_loader.mis_loader_v1 import load_mis_v1
from app.services.sample_loader.mis_loader_v2 import load_mis_v2
from app.services.sample_loader.portfolio_loader import (
    ParsedCompany,
    ParsedTransaction,
    load_portfolio,
)

app = typer.Typer(help="NKSquared backend admin commands.")


@app.callback()
def _root() -> None:
    """Marker callback so Typer keeps `create-admin` as a named subcommand."""


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(..., "--email", help="Admin email."),
    password: str = typer.Option(..., "--password", help="Admin password (min 8 chars)."),
    name: str = typer.Option(..., "--name", help="Admin full name."),
) -> None:
    """Create the bootstrap ADMIN user. Idempotent — re-running is a no-op."""
    if len(password) < 8:
        typer.echo("password must be at least 8 characters")
        raise typer.Exit(code=2)

    with SessionLocal() as db:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing is not None:
            typer.echo(f"user {email!r} already exists (id={existing.id}, role={existing.role}); nothing to do")
            return

        user = User(
            email=email,
            full_name=name,
            password_hash=hash_password(password),
            role="ADMIN",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        typer.echo(f"created ADMIN user {user.email!r} (id={user.id})")


def _signed_amount(parsed: ParsedTransaction) -> Decimal:
    if parsed.transaction_type in NEGATIVE_TYPES:
        return -parsed.amount_cr
    if parsed.transaction_type in POSITIVE_TYPES:
        return parsed.amount_cr
    return Decimal("0")


def _wipe_portfolio_tables(db) -> dict[str, int]:
    """Reset all portfolio + MIS tables. FX rates, users, and audit_log are preserved."""
    counts = {}
    for table in [
        "mis_outlet_monthly",
        "mis_bu_monthly",
        "mis_monthly",
        "mis_submissions",
        "valuations",
        "portfolio_transactions",
        "portfolio_companies",
    ]:
        result = db.execute(text(f"DELETE FROM {table}"))
        counts[table] = result.rowcount or 0
    # Reset SERIAL sequences so loaded ids start at 1.
    for seq in [
        "portfolio_companies_id_seq",
        "portfolio_transactions_id_seq",
        "valuations_id_seq",
        "mis_submissions_id_seq",
        "mis_monthly_id_seq",
        "mis_bu_monthly_id_seq",
        "mis_outlet_monthly_id_seq",
    ]:
        db.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))
    return counts


def _bu_to_mis_kwargs(row, submission_id: int) -> dict:
    """Filter dataclass fields to those the MisBuMonthly model accepts."""
    model_columns = {c.name for c in MisBuMonthly.__table__.columns}
    data = {f.name: getattr(row, f.name) for f in fields(row)}
    data["submission_id"] = submission_id
    return {k: v for k, v in data.items() if k in model_columns}


def _monthly_to_mis_kwargs(row, submission_id: int) -> dict:
    model_columns = {c.name for c in MisMonthly.__table__.columns}
    data = {f.name: getattr(row, f.name) for f in fields(row)}
    data["submission_id"] = submission_id
    return {k: v for k, v in data.items() if k in model_columns}


@app.command("load-samples")
def load_samples(
    samples_dir: Path = typer.Option(
        Path("/samples"), "--samples-dir", help="Directory containing the sample workbooks."
    ),
    reset: bool = typer.Option(
        True, "--reset/--no-reset", help="Wipe portfolio + MIS tables before loading."
    ),
) -> None:
    """Wipe demo data and ingest the sample workbooks under `samples/`."""
    portfolio_xlsm = samples_dir / "Copy of Portolfio_Base_Structure.xlsm"
    mis_v1_xlsx = samples_dir / "Company_01_Mock MIS_FY26.xlsx"
    mis_v2_xlsx = samples_dir / "Company_02_Mock MIS_FY26.xlsx"

    if not portfolio_xlsm.exists():
        typer.echo(f"missing: {portfolio_xlsm}")
        raise typer.Exit(code=2)

    typer.echo(f"parsing {portfolio_xlsm}…")
    parsed_companies = load_portfolio(portfolio_xlsm)
    typer.echo(f"  parsed {len(parsed_companies)} companies")

    parsed_mis_v1 = None
    if mis_v1_xlsx.exists():
        typer.echo(f"parsing {mis_v1_xlsx}…")
        parsed_mis_v1 = load_mis_v1(mis_v1_xlsx, company_id="company_01")
        typer.echo(
            f"  parsed {len(parsed_mis_v1.monthly_rows)} monthly + {len(parsed_mis_v1.bu_rows)} bu rows"
        )

    parsed_mis_v2 = None
    if mis_v2_xlsx.exists():
        typer.echo(f"parsing {mis_v2_xlsx}…")
        parsed_mis_v2 = load_mis_v2(mis_v2_xlsx, company_id="company_02")
        typer.echo(
            f"  parsed {len(parsed_mis_v2.monthly_rows)} monthly + {len(parsed_mis_v2.bu_rows)} bu rows"
        )

    with SessionLocal() as db:
        if reset:
            counts = _wipe_portfolio_tables(db)
            db.add(
                AuditLog(
                    user_id=None,
                    entity_type="sample_loader",
                    entity_id=0,
                    action="LOAD_SAMPLES",
                    new_value=f"reset {counts}",
                )
            )
            typer.echo(f"wiped {sum(counts.values())} existing rows")

        # Insert companies + transactions + valuations.
        n_companies = 0
        n_txns = 0
        n_valuations = 0
        for parsed in parsed_companies:
            company = PortfolioCompany(
                company_name=parsed.company_name,
                display_name=parsed.display_name,
                portfolio_type=parsed.portfolio_type,
                investment_status=parsed.investment_status,
                portfolio_status=parsed.portfolio_status,
                asset_class=parsed.asset_class,
                sector=parsed.sector,
                sub_sector=parsed.sub_sector,
                country=parsed.country,
                date_of_first_investment=parsed.date_of_first_investment,
                current_value_cr=parsed.current_value_cr,
                currency=parsed.currency,
                reporting_frequency="Monthly",
                is_active=True,
            )
            db.add(company)
            db.flush()  # populate company.id
            n_companies += 1

            for ptx in parsed.transactions:
                amount_cr_signed = _signed_amount(ptx)
                amount_inr_cr = amount_cr_signed if parsed.currency == "INR" else None
                fx_rate = Decimal("1") if parsed.currency == "INR" else None
                notes_extra = (
                    f"Original Type: {ptx.raw_txn_type}" if ptx.raw_txn_type else None
                )
                db.add(
                    PortfolioTransaction(
                        company_id=company.id,
                        transaction_date=ptx.transaction_date,
                        transaction_type=ptx.transaction_type,
                        amount_cr=amount_cr_signed,
                        original_currency=parsed.currency,
                        original_amount=ptx.amount_cr,
                        amount_inr_cr=amount_inr_cr,
                        fx_rate_used=fx_rate,
                        series=ptx.series,
                        instrument_type=ptx.instrument_type,
                        investing_entity=ptx.investing_entity,
                        shares=ptx.shares,
                        share_price=ptx.share_price,
                        pre_money_valuation_cr=ptx.pre_money_valuation_cr,
                        post_money_valuation_cr=ptx.post_money_valuation_cr,
                        shareholding_pct=ptx.shareholding_pct,
                        notes=notes_extra,
                    )
                )
                n_txns += 1

            if parsed.valuation is not None:
                db.add(
                    Valuation(
                        company_id=company.id,
                        valuation_date=parsed.valuation.valuation_date,
                        post_money_valuation_cr=parsed.valuation.post_money_valuation_cr,
                        pre_money_valuation_cr=parsed.valuation.pre_money_valuation_cr,
                        currency=parsed.currency,
                        source="Internal",
                        notes="Loaded from sample portfolio",
                    )
                )
                n_valuations += 1

        db.flush()

        # Insert MIS submissions (use string company_id per § 3.3 convention).
        n_mis_submissions = 0
        n_mis_monthly = 0
        n_mis_bu = 0
        for parsed_mis in (parsed_mis_v1, parsed_mis_v2):
            if parsed_mis is None:
                continue
            submission = MisSubmission(
                company_id=parsed_mis.company_id,
                period_year=parsed_mis.period_year,
                period_month=parsed_mis.period_month,
                fiscal_year=parsed_mis.fiscal_year,
                status="Approved",
                source_file_name=parsed_mis.source_file_name,
                anomaly_count=0,
            )
            db.add(submission)
            db.flush()
            n_mis_submissions += 1

            for r in parsed_mis.monthly_rows:
                db.add(MisMonthly(**_monthly_to_mis_kwargs(r, submission.id)))
                n_mis_monthly += 1
            for r in parsed_mis.bu_rows:
                db.add(MisBuMonthly(**_bu_to_mis_kwargs(r, submission.id)))
                n_mis_bu += 1

        db.flush()

        # Recompute MOIC + IRR for every loaded company.
        loaded_ids = list(db.execute(select(PortfolioCompany.id)).scalars().all())
        for cid in loaded_ids:
            metrics_service.recompute_company_metrics(db, cid)

        db.commit()

    typer.echo(
        f"loaded {n_companies} companies, {n_txns} transactions, {n_valuations} valuations, "
        f"{n_mis_submissions} MIS submissions, {n_mis_monthly} mis_monthly + {n_mis_bu} mis_bu rows"
    )


if __name__ == "__main__":
    app()
