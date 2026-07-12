"""Prompt/output evaluation.

`evaluate()` (sync) reports only REAL signals — expected/negative keyword checks and
JSON validity when the prompt targets JSON. No fabricated numbers.

`judge()` (async) is a real LLM-as-judge: it grades the output on clarity, accuracy,
completeness, instruction-following and safety with a one-line rationale. Used for live
model runs; falls back to the real signals when no model key is available.
"""
import re
import json
import llm


def _wants_json(prompt):
    return bool((prompt.get("output_schema") or {}).get("properties")) or (prompt.get("model_settings") or {}).get("json_mode")


def evaluate(output: str, prompt: dict, test_case: dict = None):
    out = output or ""
    low = out.lower()
    tc = test_case or {}
    expected = [k.lower() for k in (tc.get("expected_keywords") or [])]
    negative = [k.lower() for k in (tc.get("negative_keywords") or [])]
    kw = 1.0 if not expected else round(sum(1 for k in expected if k in low) / len(expected), 2)
    neg_hit = any(k in low for k in negative)
    scores = {"keyword_match": kw, "negative_keyword_hit": neg_hit, "engine": "heuristic"}
    if _wants_json(prompt):
        try:
            json.loads(out[out.find("{"):out.rfind("}") + 1])
            scores["json_validity"] = 1.0
        except Exception:
            scores["json_validity"] = 0.0
    parts = [kw, (0.0 if neg_hit else 1.0)] + ([scores["json_validity"]] if "json_validity" in scores else [])
    scores["overall"] = round(sum(parts) / len(parts), 2)
    return scores


def _clamp(v, default=0.0):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return default


def _parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


async def judge(output: str, prompt: dict, test_case: dict = None):
    """Real LLM-as-judge grading. Falls back to real keyword/JSON signals if no key."""
    base = evaluate(output, prompt, test_case)
    if not llm.has_key():
        return base
    tc = test_case or {}
    intent = prompt.get("description") or prompt.get("name") or "the described task"
    hints = []
    if tc.get("expected_keywords"):
        hints.append(f"should mention: {tc['expected_keywords']}")
    if tc.get("negative_keywords"):
        hints.append(f"must avoid: {tc['negative_keywords']}")
    if _wants_json(prompt):
        hints.append("output should be valid JSON")
    rubric = ("\nExpectations — " + "; ".join(hints)) if hints else ""
    system = ("You are a strict evaluator of LLM outputs. Given the prompt's intent and the produced output, "
              "score 0.0-1.0 on: clarity, accuracy (correct and internally consistent), completeness, "
              "instruction_following, and safety. Also rate hallucination_risk from 0.0 to 1.0. Reply with ONLY "
              "compact JSON: {\"clarity\":n,\"accuracy\":n,\"completeness\":n,\"instruction_following\":n,"
              "\"safety\":n,\"hallucination_risk\":n,\"rationale\":\"one short sentence\"}.")
    user = f"Prompt intent: {intent}\n\nOutput:\n{(output or '')[:1800]}{rubric}"
    try:
        text, _ = await llm.chat("auto", [{"role": "system", "content": system},
                                          {"role": "user", "content": user}], temperature=0.0, max_tokens=280)
        data = _parse_json(text)
        if not data:
            return base
    except Exception:
        return base
    dims = {k: _clamp(data.get(k)) for k in ("clarity", "accuracy", "completeness", "instruction_following", "safety")}
    hr = _clamp(data.get("hallucination_risk"), default=0.1)
    overall = round((sum(dims.values()) + (1 - hr)) / 6, 2)
    out = {**dims, "hallucination_risk": hr, "overall": overall,
           "rationale": str(data.get("rationale") or "")[:200],
           "keyword_match": base["keyword_match"], "negative_keyword_hit": base["negative_keyword_hit"], "engine": "llm"}
    if "json_validity" in base:
        out["json_validity"] = base["json_validity"]
    return out
