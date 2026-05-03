"""One-shot backfill: populate `portfolio_companies.company_code` from the
existing `company_name` column.

The MIS pipeline keys everything off a string code like `company_01`, while
portfolio_companies were seeded with names like `Company_01`. This script
lowercases the canonical name when it matches the `Company_NN` shape,
leaving rows that don't match (`null`) for an analyst to fill manually.

Idempotent: no-ops on rows that already have a code, and never overwrites.

Usage::

    python -m app.services.sample_loader.backfill_company_codes
"""
from __future__ import annotations

import re
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.company import PortfolioCompany

_PATTERN = re.compile(r"^company_\d+$", re.IGNORECASE)


def backfill() -> tuple[int, int]:
    """Returns (updated, skipped)."""
    updated = 0
    skipped = 0
    with SessionLocal() as db:
        rows = db.execute(select(PortfolioCompany)).scalars().all()
        for c in rows:
            if c.company_code:
                skipped += 1
                continue
            name = (c.company_name or "").strip()
            # Strip a "_Display" suffix that some seed rows pick up.
            base = name.split("_Display")[0]
            if _PATTERN.match(base):
                c.company_code = base.lower()
                updated += 1
            else:
                skipped += 1
        db.commit()
    return updated, skipped


def main() -> int:
    updated, skipped = backfill()
    print(f"Backfilled {updated} company_code values; skipped {skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
