"""Deterministic mock model providers for the Test Lab. Each provider returns a
distinct style so the comparison view is meaningful. Seam for real Nyquest routing:
set ENABLE_MOCK_MODELS=false and wire a real client keyed by provider/model."""
import os
import hashlib

MOCK = os.environ.get("ENABLE_MOCK_MODELS", "true").lower() != "false"

# provider key -> (label, style_fn, price_per_1k, base_latency_ms, quality_bias)
PROVIDERS = [
    {"key": "openai", "label": "OpenAI", "model": "gpt-5", "price": 0.010, "latency": 900, "q": 0.90},
    {"key": "anthropic", "label": "Claude", "model": "claude-sonnet-5", "price": 0.009, "latency": 1100, "q": 0.93},
    {"key": "google", "label": "Gemini", "model": "gemini-2.5-flash", "price": 0.004, "latency": 600, "q": 0.86},
    {"key": "meta", "label": "Llama", "model": "llama-4-70b", "price": 0.002, "latency": 700, "q": 0.82},
    {"key": "mistral", "label": "Mistral", "model": "mistral-large", "price": 0.003, "latency": 650, "q": 0.83},
    {"key": "nyquest-router", "label": "Nyquest Router", "model": "auto", "price": 0.005, "latency": 750, "q": 0.94},
]
BY_KEY = {p["key"]: p for p in PROVIDERS}


def _hash(s):
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


def _core_answer(rendered, values):
    """A believable, input-aware answer body shared across providers."""
    msg = (values.get("customer_message") or values.get("user_prompt") or values.get("visitor_question")
           or values.get("customer") or values.get("issue_description") or values.get("lead_message")
           or values.get("alert_text") or values.get("document_text") or "")
    biz = values.get("business_name") or values.get("company_name") or values.get("university_name") or "our team"
    if msg:
        return f'Regarding "{str(msg)[:90]}": here is a clear, grounded answer for {biz}, using only the provided context and asking for clarification if something is missing.'
    return f"A clear, grounded response for {biz} that follows the system instructions and stays within the provided context."


def _style(provider_key, core):
    if provider_key == "openai":
        return f"{core}\n\n1. Direct answer.\n2. One next step.\nStructured and concise."
    if provider_key == "anthropic":
        return f"{core}\n\nI'll walk through this carefully: the key point, the reasoning behind it, and a warm, polished closing — thorough without being verbose."
    if provider_key == "google":
        return f"{core} Short and fast."
    if provider_key == "meta":
        return f"{core}\nPlain, open-source-style answer. Gets the job done."
    if provider_key == "mistral":
        return f"{core}\nEfficient, to the point, lightly formatted."
    if provider_key == "nyquest-router":
        return f"{core}\n\n[Nyquest Router] Balanced answer routed for best cost/quality — compression applied automatically."
    return core


def run(provider_key, rendered, values, model_settings=None):
    p = BY_KEY.get(provider_key, BY_KEY["nyquest-router"])
    core = _core_answer(rendered, values or {})
    output = _style(p["key"], core)
    seed = _hash(p["key"] + rendered[:200])
    tokens = 120 + len(rendered) // 4 + (seed % 180)
    cost = round(tokens / 1000 * p["price"], 5)
    latency = p["latency"] + (seed % 400)
    quality = round(min(0.99, p["q"] + (seed % 7 - 3) / 100.0), 2)
    risk = round(max(0.02, 0.12 - (seed % 8) / 100.0), 2)
    return {
        "provider": p["key"], "label": p["label"], "model": p["model"],
        "output": output,
        "metrics": {"token_estimate": tokens, "cost_estimate": cost, "latency_ms": latency,
                    "quality_score": quality, "risk_score": risk},
        "latency_ms": latency, "cost_estimate": cost, "token_estimate": tokens,
    }
