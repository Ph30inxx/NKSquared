"""
Request-scoped context storage.

Stores the analyst's raw JWT token for the duration of each /chat request
so write tools can forward it to the backend API without it being passed
as an explicit parameter through every function call.
"""
import contextvars

_auth_token: contextvars.ContextVar[str] = contextvars.ContextVar("_auth_token", default="")


def get_auth_token() -> str:
    return _auth_token.get()


def set_auth_token(token: str) -> contextvars.Token:
    return _auth_token.set(token)


def reset_auth_token(reset_token: contextvars.Token) -> None:
    _auth_token.reset(reset_token)
