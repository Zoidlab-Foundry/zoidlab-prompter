"""Model runner — routes a rendered prompt to a real Nyquest model (billed to the
signed-in user's wallet via their relay key) with a deterministic mock fallback."""
import os
import time
import renderer
import mockmodels
import llm

REAL = os.environ.get("ENABLE_REAL_MODEL_ROUTING", "true").lower() != "false"


def _messages(sections):
    system = "\n\n".join(x for x in [sections.get("system_prompt"), sections.get("developer_prompt"),
                                     sections.get("tool_prompt")] if x)
    user = sections.get("user_prompt") or "(no user input)"
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return msgs


def _label(model_id):
    if model_id == "auto":
        return "Nyquest Router"
    return (model_id.split("/")[-1] if "/" in model_id else model_id).replace("-preview", "")


async def run(model_id, prompt, values):
    """Run one model. Returns the same shape as mockmodels.run (output + metrics)."""
    r = renderer.render_prompt(prompt, values or {})
    ms = prompt.get("model_settings") or {}
    if REAL and llm.has_key():
        try:
            t0 = time.time()
            text, usage = await llm.chat(model_id, _messages(r["sections"]),
                                         temperature=float(ms.get("temperature", 0.4)),
                                         max_tokens=int(ms.get("max_tokens", 800)))
            latency = int((time.time() - t0) * 1000)
            tokens = usage.get("total_tokens") or 0
            cost = llm.cost_estimate(model_id, tokens)
            billing = llm.billing_mode()  # "user" (their wallet) | "owner" (shared key)
            return {"provider": model_id, "label": _label(model_id), "model": model_id, "output": text,
                    "metrics": {"token_estimate": tokens, "cost_estimate": cost, "latency_ms": latency,
                                "quality_score": None, "risk_score": None, "live": True, "billing": billing},
                    "latency_ms": latency, "cost_estimate": cost, "token_estimate": tokens, "live": True, "billing": billing}
        except Exception as e:
            # surface the error but don't crash the comparison grid
            return {"provider": model_id, "label": _label(model_id), "model": model_id,
                    "output": f"[model error] {str(e)[:200]}",
                    "metrics": {"token_estimate": 0, "cost_estimate": 0, "latency_ms": 0, "error": True},
                    "latency_ms": 0, "cost_estimate": 0, "token_estimate": 0, "error": True}
    # mock fallback (keyless / disabled) — map the full model id to the right provider
    # style by its prefix, so "anthropic/…" renders as Claude, "google/…" as Gemini, etc.
    # (previously every non-bare id collapsed to the OpenAI style).
    if model_id == "auto":
        key = "nyquest-router"
    else:
        prefix = model_id.split("/")[0] if "/" in model_id else model_id
        alias = {"meta-llama": "meta", "meta_llama": "meta", "llama": "meta", "mistralai": "mistral"}
        prefix = alias.get(prefix, prefix)
        key = prefix if prefix in mockmodels.BY_KEY else "openai"
    res = mockmodels.run(key, r["combined"], values or {}, ms)
    res["model"] = model_id
    res["label"] = _label(model_id)
    res["billing"] = "mock"
    res.setdefault("metrics", {})["billing"] = "mock"
    return res
