from __future__ import annotations

import typer
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User

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


if __name__ == "__main__":
    app()
