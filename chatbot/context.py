"""
Request-scoped context storage.

Stores the analyst's raw JWT token for the duration of each /chat request
so write tools can forward it to the backend API without it being passed
as an explicit parameter through every function call.

Also stores a voice-mode flag so write tools can automatically skip the
dry_run preview step when invoked from a voice session (where verbal
confirmation has already been obtained by the Vapi layer).
"""
import contextvars

_auth_token: contextvars.ContextVar[str] = contextvars.ContextVar("_auth_token", default="")
_voice_mode: contextvars.ContextVar[bool] = contextvars.ContextVar("_voice_mode", default=False)


def get_auth_token() -> str:
    return _auth_token.get()


def set_auth_token(token: str) -> contextvars.Token:
    return _auth_token.set(token)


def reset_auth_token(reset_token: contextvars.Token) -> None:
    _auth_token.reset(reset_token)


def is_voice_mode() -> bool:
    return _voice_mode.get()


def set_voice_mode(enabled: bool) -> contextvars.Token:
    return _voice_mode.set(enabled)


def reset_voice_mode(reset_token: contextvars.Token) -> None:
    _voice_mode.reset(reset_token)

