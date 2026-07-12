"""Heuristic prompt/output evaluation. Real Nyquest Evaluation Lab plugs in later."""
import json
import hashlib


def _score(seed_str, lo, hi):
    h = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    span = int((hi - lo) * 100)
    return round(lo + (h % (span + 1)) / 100.0, 2)


def evaluate(output: str, prompt: dict, test_case: dict = None):
    """Return category scores + overall (0–1). Keyword checks are real; the rest
    are heuristic placeholders until real evaluators are wired in."""
    out = output or ""
    low = out.lower()
    tc = test_case or {}
    expected = [k.lower() for k in (tc.get("expected_keywords") or [])]
    negative = [k.lower() for k in (tc.get("negative_keywords") or [])]

    hits = sum(1 for k in expected if k in low)
    kw = 1.0 if not expected else round(hits / len(expected), 2)
    neg_hit = any(k in low for k in negative)

    # JSON validity if the prompt targets JSON output
    wants_json = bool((prompt.get("output_schema") or {}).get("properties")) or (prompt.get("model_settings") or {}).get("json_mode")
    json_valid = 1.0
    if wants_json:
        try:
            json.loads(out[out.find("{"):out.rfind("}") + 1]); json_valid = 1.0
        except Exception:
            json_valid = 0.4

    seed = (prompt.get("id") or "") + out[:120]
    scores = {
        "clarity": _score("cl" + seed, 0.80, 0.97),
        "accuracy": max(0.4, kw) if expected else _score("ac" + seed, 0.78, 0.95),
        "completeness": _score("co" + seed, 0.75, 0.95),
        "tone_match": _score("to" + seed, 0.80, 0.96),
        "safety": 0.5 if neg_hit else _score("sa" + seed, 0.88, 0.98),
        "policy_compliance": _score("po" + seed, 0.85, 0.98),
        "json_validity": json_valid,
        "hallucination_risk": _score("ha" + seed, 0.06, 0.20),
        "injection_resistance": _score("in" + seed, 0.82, 0.97),
        "keyword_match": kw,
    }
    # overall = mean of positive-direction metrics (invert hallucination risk)
    pos = [scores["clarity"], scores["accuracy"], scores["completeness"], scores["tone_match"],
           scores["safety"], scores["policy_compliance"], scores["json_validity"], scores["injection_resistance"],
           1 - scores["hallucination_risk"]]
    scores["overall"] = round(sum(pos) / len(pos), 2)
    scores["negative_keyword_hit"] = neg_hit
    return scores
