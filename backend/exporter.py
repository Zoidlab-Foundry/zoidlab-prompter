"""Nyquest Prompt Package — the portable prompt export format (prompt.package.json)
plus a human-readable Markdown export."""


def to_package(prompt: dict, test_cases=None) -> dict:
    ms = prompt.get("model_settings") or {}
    gov = prompt.get("governance") or {}
    return {
        "schema_version": "1.0",
        "prompt_id": prompt.get("slug") or prompt.get("id"),
        "name": prompt.get("name"),
        "version": prompt.get("current_version", "0.1.0"),
        "description": prompt.get("description", ""),
        "category": prompt.get("category", "General"),
        "tags": prompt.get("tags", []),
        "prompt": {
            "system": prompt.get("system_prompt", ""),
            "developer": prompt.get("developer_prompt", ""),
            "user": prompt.get("user_prompt", ""),
            "tool": prompt.get("tool_prompt", ""),
        },
        "variables": prompt.get("variables", []),
        "model_settings": ms,
        "output_schema": prompt.get("output_schema", {}),
        "governance": gov,
        "test_cases": [
            {"name": t.get("name"), "input": t.get("input_variables", {}),
             "expected_keywords": t.get("expected_keywords", []),
             "negative_keywords": t.get("negative_keywords", [])}
            for t in (test_cases or [])
        ],
    }


def to_markdown(prompt: dict, test_cases=None) -> str:
    ms = prompt.get("model_settings") or {}
    gov = prompt.get("governance") or {}
    L = []
    L.append(f"# {prompt.get('name')}")
    L.append(f"**Version:** {prompt.get('current_version', '0.1.0')} · **Category:** {prompt.get('category', 'General')} "
             f"· **Status:** {prompt.get('status', 'draft')} · **Risk:** {gov.get('risk_level', prompt.get('risk_level', 'low'))}")
    if prompt.get("description"):
        L.append(f"\n{prompt['description']}")
    for key, title in [("system_prompt", "System prompt"), ("developer_prompt", "Developer prompt"),
                       ("user_prompt", "User prompt"), ("tool_prompt", "Tool / function instructions")]:
        if prompt.get(key):
            L.append(f"\n## {title}\n\n```\n{prompt[key]}\n```")
    variables = prompt.get("variables", [])
    if variables:
        L.append("\n## Variables\n")
        L.append("| Name | Type | Required | Description | Example |")
        L.append("|------|------|----------|-------------|---------|")
        for v in variables:
            L.append(f"| `{{{{{v.get('name')}}}}}` | {v.get('type', 'string')} | {'yes' if v.get('required') else 'no'} "
                     f"| {v.get('description', '')} | {v.get('example', '')} |")
    L.append("\n## Model settings\n")
    L.append(f"- Provider: `{ms.get('provider', 'nyquest-router')}` · Model: `{ms.get('model', 'auto')}`")
    L.append(f"- Temperature: {ms.get('temperature', 0.4)} · Max tokens: {ms.get('max_tokens', 800)} "
             f"· JSON mode: {ms.get('json_mode', False)} · Fallback: `{ms.get('fallback_model', '')}`")
    L.append("\n## Governance\n")
    for k in ("risk_level", "pii_risk", "requires_human_approval", "logs_prompts", "logs_outputs", "approved_for_production"):
        L.append(f"- {k.replace('_', ' ').title()}: {gov.get(k)}")
    if test_cases:
        L.append("\n## Test cases\n")
        for t in test_cases:
            L.append(f"- **{t.get('name')}** — input `{t.get('input_variables', {})}`, "
                     f"expect {t.get('expected_keywords', [])}, avoid {t.get('negative_keywords', [])}")
    return "\n".join(L) + "\n"
