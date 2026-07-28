"""Prompter assistant manifest — what the in-app assistant knows and may do.

The security boundary: only these capabilities exist for the assistant, and they run through
this app's own session-authed API. Deletes, approval decisions (human judgment) and
deploy/undeploy are deliberately NOT exposed.
"""
from foundry_common.assistant import cap, page

MANIFEST = {
    "app": "Prompter",
    "description": (
        "Prompter is the enterprise prompt lifecycle studio: author prompts with "
        "{{variables}} across system/developer/user sections, prove them in the Test Lab "
        "against real models, snapshot immutable versions you can diff and restore, route "
        "them through approval before release, and deploy an approved prompt as a "
        "token-authed API. Test runs are real relay calls billed to the user's own wallet."
    ),
    "base_url": "http://127.0.0.1:8400",
    "pages": [
        page("/", "Dashboard", "Overview: prompt counts, recent activity, approvals waiting."),
        page("/prompts", "Library", "All prompts with category, risk and status filters.",
             assists={"new-prompt": "the New prompt button"}),
        page("/prompts/[id]", "Editor", "Edit a prompt's sections and variables; snapshot versions."),
        page("/prompts/[id]/test", "Test Lab", "Run the prompt against real models with sample variables.",
             assists={"run-test": "the Run test button"}),
        page("/approvals", "Approvals", "Review queue — approve or reject prompts (human decision only)."),
        page("/templates", "Templates", "Start from a curated template."),
    ],
    "capabilities": [
        cap("list_projects", "GET", "/api/projects", risk="read",
            desc="The user's prompt projects."),
        cap("list_prompts", "GET", "/api/prompts", risk="read",
            desc="The user's prompts with status, category and risk."),
        cap("get_prompt", "GET", "/api/prompts/{pid}", risk="read",
            desc="One prompt: its sections, variables and current status.", params={"pid": "prompt id"}),
        cap("list_versions", "GET", "/api/prompts/{pid}/versions", risk="read",
            desc="Immutable version snapshots of a prompt.", params={"pid": "prompt id"}),
        cap("stats", "GET", "/api/stats", risk="read",
            desc="Counts of prompts, versions, tests and pending approvals."),
        cap("create_prompt", "POST", "/api/prompts", risk="write",
            desc="Create a prompt. Use {{variable}} placeholders in the section bodies; declare "
                 "each one in variables so the Test Lab can fill it.",
            params={"name": "prompt name", "description": "short description",
                    "category": "category label", "risk": "low|medium|high",
                    "system": "system section", "developer": "developer section",
                    "user": "user section", "variables": "list of variable definitions",
                    "project_id": "project id (optional)"}),
        cap("save_version", "POST", "/api/prompts/{pid}/versions", risk="write",
            desc="Snapshot the prompt's current content as a new immutable version.",
            params={"pid": "prompt id", "note": "what changed in this version"}),
        cap("run_test", "POST", "/api/prompts/{pid}/test", risk="write",
            desc="Run the prompt against a real model with the given variables. Billed to the "
                 "user's own Nyquest wallet.",
            params={"pid": "prompt id", "variables": "object of variable values",
                    "model": "model id (optional)"}),
    ],
}
