"""Shared ZoidLab session — decode the `zb_session` cookie minted by the SSO
handoff (jose HS256, BUILDER_SESSION_SECRET). Same cookie the other ZoidLab apps
use, so signing in once anywhere in *.zoidlab.ai authenticates here too."""
import os
import jwt
from fastapi import Request

SECRET = os.environ.get("BUILDER_SESSION_SECRET", "dev-secret-change-me")


def session(request: Request):
    tok = request.cookies.get("zb_session")
    if not tok:
        return None
    try:
        return jwt.decode(tok, SECRET, algorithms=["HS256"])
    except Exception:
        return None


def owner_of(request: Request):
    s = session(request)
    return s.get("sub") if s else None


def relay_key(request: Request):
    """The user's own minted Nyquest relay key (rk claim) — bills their wallet."""
    s = session(request)
    return s.get("rk") if s else None


def tier(request: Request):
    s = session(request)
    return (s.get("tier") if s else None) or "free"
