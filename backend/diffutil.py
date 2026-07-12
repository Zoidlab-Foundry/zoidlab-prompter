"""Version diff — line-level added/removed per section + field-level changes."""
import difflib
import json

SECTIONS = ["system_prompt", "developer_prompt", "user_prompt", "tool_prompt"]


def _line_diff(a, b):
    a_lines = (a or "").splitlines()
    b_lines = (b or "").splitlines()
    out = []
    for line in difflib.ndiff(a_lines, b_lines):
        tag = line[:2]
        if tag == "  ":
            out.append({"op": "same", "text": line[2:]})
        elif tag == "- ":
            out.append({"op": "del", "text": line[2:]})
        elif tag == "+ ":
            out.append({"op": "add", "text": line[2:]})
    return out


def diff(old: dict, new: dict):
    """old/new are version-like dicts. Returns per-section line diffs + field changes."""
    sections = {}
    for s in SECTIONS:
        oa, ob = old.get(s) or "", new.get(s) or ""
        if oa != ob:
            sections[s] = _line_diff(oa, ob)
    fields = []
    for f in ("model_settings", "output_schema", "governance", "variables"):
        ov, nv = old.get(f), new.get(f)
        if json.dumps(ov, sort_keys=True) != json.dumps(nv, sort_keys=True):
            fields.append({"field": f, "old": ov, "new": nv})
    return {"sections": sections, "fields": fields,
            "changed": bool(sections or fields),
            "old_version": old.get("version"), "new_version": new.get("version")}
