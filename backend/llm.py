"""Nyquest relay client — OpenAI-compatible gateway at NYQUEST_BASE_URL.

Per-request auth uses the signed-in user's OWN relay key (the `rk` claim minted
into the shared session cookie), so model runs bill THEIR Nyquest wallet. Falls
back to the shared owner key only when no user key is present.
"""
import os
import httpx
from contextvars import ContextVar

BASE = os.environ.get("NYQUEST_BASE_URL", "https://api.nyquest.ai/v1").rstrip("/")
KEY = os.environ.get("NYQUEST_API_KEY", "")
DEFAULT_MODEL = os.environ.get("PROMPTER_DEFAULT_MODEL", "anthropic/claude-sonnet-5")

_relay_auth: ContextVar = ContextVar("relay_auth", default=None)


def set_relay_auth(value):
    _relay_auth.set(value or None)


def _auth():
    return _relay_auth.get() or KEY


def has_key():
    return bool(_auth())


def _headers():
    return {"Authorization": f"Bearer {_auth()}", "Content-Type": "application/json"}


async def chat(model, messages, temperature=0.4, max_tokens=800):
    """Returns (text, usage_dict). Raises on transport/HTTP error."""
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            f"{BASE}/chat/completions",
            headers=_headers(),
            json={"model": model or DEFAULT_MODEL, "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"relay {r.status_code}: {r.text[:200]}")
        j = r.json()
        text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return text, j.get("usage", {}) or {}


_MODELS_CACHE = {"ids": None}


async def list_models():
    """All relay model ids (for the picker). Cached; never raises."""
    if _MODELS_CACHE["ids"]:
        return _MODELS_CACHE["ids"]
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{BASE}/models", headers={"Authorization": f"Bearer {KEY}"})
            r.raise_for_status()
            ids = sorted(m.get("id") for m in r.json().get("data", []) if m.get("id"))
            _MODELS_CACHE["ids"] = ids
            return ids
    except Exception:
        return ["auto", "anthropic/claude-sonnet-5", "anthropic/claude-opus-4-8",
                "openai/gpt-5", "openai/gpt-5-mini", "google/gemini-2.5-pro",
                "google/gemini-2.5-flash", "meta-llama/llama-4-70b", "mistralai/mistral-large"]


FEATURED_HINTS = ["claude-sonnet-5", "claude-opus-4-8", "gpt-5", "gemini-2.5-pro",
                  "gemini-2.5-flash", "llama-4", "mistral-large"]
_EXCLUDE = ("image", "audio", "video", "tts", "whisper", "embed", "dall", "veo",
            "imagen", "lyria", "music", "rerank", "moderation", "-realtime")


def _text_only(ids):
    return [i for i in ids if not any(x in i.lower() for x in _EXCLUDE)]


async def featured_models():
    ids = _text_only(await list_models())
    out = ["auto"]
    for hint in FEATURED_HINTS:
        m = next((i for i in ids if hint in i.lower()), None)
        if m and m not in out:
            out.append(m)
    return out


# rough per-1k-token USD estimate for the cost column (real billing is on the wallet)
def cost_estimate(model_id, tokens):
    m = (model_id or "").lower()
    price = 0.005
    if "opus" in m or "gpt-5" in m and "mini" not in m:
        price = 0.012
    elif "sonnet" in m or "gemini-2.5-pro" in m:
        price = 0.008
    elif "mini" in m or "flash" in m or "haiku" in m:
        price = 0.002
    elif "llama" in m or "mistral" in m:
        price = 0.002
    return round((tokens or 0) / 1000 * price, 5)
