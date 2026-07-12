"""Prompt template rendering — {{variable}} substitution + built-ins."""
import re
import json
import datetime

_VAR = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def _builtins():
    return {"current_date": datetime.date.today().isoformat(),
            "now": datetime.datetime.utcnow().isoformat() + "Z"}


def render_text(text, values):
    if not text:
        return ""
    def sub(m):
        k = m.group(1)
        v = values.get(k)
        if v is None:
            return m.group(0)  # leave unresolved so it's visible
        return v if isinstance(v, str) else json.dumps(v)
    return _VAR.sub(sub, text)


def variables_in(*texts):
    found = []
    for t in texts:
        for m in _VAR.finditer(t or ""):
            if m.group(1) not in found:
                found.append(m.group(1))
    return found


def render_prompt(prompt: dict, values: dict):
    """Render every section. Returns {sections, combined, used, missing}."""
    vals = {**_builtins(), **(values or {})}
    sections = {k: render_text(prompt.get(k, ""), vals)
                for k in ("system_prompt", "developer_prompt", "user_prompt", "tool_prompt")}
    used = variables_in(prompt.get("system_prompt"), prompt.get("developer_prompt"),
                        prompt.get("user_prompt"), prompt.get("tool_prompt"))
    missing = [v for v in used if v not in vals or vals.get(v) in (None, "")]
    parts = []
    if sections["system_prompt"]:
        parts.append("### SYSTEM\n" + sections["system_prompt"])
    if sections["developer_prompt"]:
        parts.append("### DEVELOPER\n" + sections["developer_prompt"])
    if sections["user_prompt"]:
        parts.append("### USER\n" + sections["user_prompt"])
    if sections["tool_prompt"]:
        parts.append("### TOOLS\n" + sections["tool_prompt"])
    return {"sections": sections, "combined": "\n\n".join(parts), "used": used, "missing": missing}
