"""Shared ZoidLab session — decode the `zb_session` cookie minted by the SSO
handoff (jose HS256, BUILDER_SESSION_SECRET). Same cookie the other ZoidLab apps
use, so signing in once anywhere in *.zoidlab.ai authenticates here too."""
import os
import sys
import jwt
from fastapi import Request

_DEFAULT = "dev-secret-change-me"
SECRET = os.environ.get("BUILDER_SESSION_SECRET", _DEFAULT)
PRO_TIERS = {"pro", "teams", "team", "enterprise"}

if SECRET == _DEFAULT:
    print("[prompter] WARNING: BUILDER_SESSION_SECRET is unset — using an insecure "
          "default. Session cookies are forgeable. Set a real secret before exposing this API.",
          file=sys.stderr)


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


def is_pro(request: Request):
    return str(tier(request)).lower() in PRO_TIERS
