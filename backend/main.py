"""ZoidLab Prompter API — prompt lifecycle: project → prompt → variables → test →
compare → version → approve → export. Public read of seed content; create/edit/
approve require the shared ZoidLab (Nyquest) session. Owner = Nyquest user id.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Any, List

import database as db
import renderer
import mockmodels
import evaluator
import diffutil
import exporter
import seed
import runner
import llm
from auth import owner_of, session, relay_key, tier, is_pro as auth_is_pro


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    n = seed.run()
    if n:
        print(f"[prompter] seeded {n} templates + example projects")
    yield


app = FastAPI(title="ZoidLab Prompter API", lifespan=lifespan)


def require_owner(request: Request):
    """Every write / model run requires a signed-in Nyquest Pro user (backend-enforced,
    so the entitlement holds even if a request skips the frontend gate)."""
    s = session(request)
    o = s.get("sub") if s else None
    if not o:
        raise HTTPException(status_code=401, detail="sign_in_required")
    if not auth_is_pro(request):
        raise HTTPException(status_code=403, detail="pro_required")
    db.upsert_user(o, s.get("email"), s.get("name"))
    return o


def badges(prompt: dict) -> List[str]:
    gov = prompt.get("governance") or {}
    risk = (gov.get("risk_level") or prompt.get("risk_level") or "low").lower()
    out = [{"low": "Low Risk", "medium": "Medium Risk", "high": "High Risk"}.get(risk, "Low Risk")]
    if prompt.get("status") in ("approved", "deployed") or gov.get("approved_for_production"):
        out.append("Approved")
    elif prompt.get("status") == "pending_approval":
        out.append("Needs Review")
    if str(gov.get("pii_risk", "")).lower() in ("medium", "high"):
        out.append("PII Risk")
    if (prompt.get("model_settings") or {}).get("json_mode") or (prompt.get("output_schema") or {}).get("properties"):
        out.append("Output Must Be JSON")
    if gov.get("requires_human_approval"):
        out.append("Human Approval Required")
    if gov.get("external_api"):
        out.append("External API")
    return out


def deco(p):
    if p:
        p["badges"] = badges(p)
    return p


# ---- meta ---------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "templates": len(db.list_templates())}


@app.get("/api/whoami")
def whoami(request: Request):
    s = session(request)
    if not s:
        return {"authenticated": False}
    return {"authenticated": True, "email": s.get("email"), "name": s.get("name"),
            "tier": s.get("tier"), "admin": db.is_admin(s.get("sub"))}


@app.get("/api/stats")
def stats(request: Request):
    return db.stats(owner_of(request))


@app.get("/api/filters")
def filters(request: Request):
    v = owner_of(request)
    return {"categories": db.counts_by("category", v), "statuses": db.counts_by("status", v),
            "risks": db.counts_by("risk_level", v)}


# ---- projects -----------------------------------------------------------
class ProjectBody(BaseModel):
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "active"
    icon: Optional[str] = "◆"
    accent: Optional[str] = "#7c5cfc"


@app.get("/api/projects")
def projects(request: Request):
    return {"projects": db.list_projects(owner_of(request))}


@app.post("/api/projects")
def create_project(body: ProjectBody, request: Request):
    o = require_owner(request)
    return {"ok": True, "project": db.create_project(body.model_dump(), o)}


@app.get("/api/projects/{pid}")
def get_project(pid: str, request: Request):
    p = db.get_project(pid, owner_of(request))
    if not p:
        raise HTTPException(404, "not_found")
    p["prompts"] = db.list_prompts(owner_of(request), project_id=pid)
    return p


@app.put("/api/projects/{pid}")
def update_project(pid: str, body: ProjectBody, request: Request):
    o = require_owner(request)
    p = db.update_project(pid, body.model_dump(), o)
    if not p:
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True, "project": p}


@app.delete("/api/projects/{pid}")
def archive_project(pid: str, request: Request):
    o = require_owner(request)
    p = db.update_project(pid, {"status": "archived"}, o)
    if not p:
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True}


# ---- prompts ------------------------------------------------------------
class PromptBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list] = None
    project_id: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    system_prompt: Optional[str] = None
    developer_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    tool_prompt: Optional[str] = None
    output_schema: Optional[dict] = None
    variables: Optional[list] = None
    model_settings: Optional[dict] = None
    governance: Optional[dict] = None
    current_version: Optional[str] = None


@app.get("/api/prompts")
def prompts(request: Request, search: Optional[str] = None, project_id: Optional[str] = None,
            category: Optional[str] = None, status: Optional[str] = None, risk_level: Optional[str] = None,
            tag: Optional[str] = None, sort: str = "updated"):
    items = db.list_prompts(owner_of(request), search=search, project_id=project_id, category=category,
                            status=status, risk=risk_level, tag=tag, sort=sort)
    for p in items:
        p["badges"] = badges(p)
    return {"prompts": items, "count": len(items)}


@app.post("/api/prompts")
def create_prompt(body: PromptBody, request: Request):
    o = require_owner(request)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data.get("name"):
        raise HTTPException(400, "name_required")
    return {"ok": True, "prompt": deco(db.create_prompt(data, o))}


@app.get("/api/prompts/{pid}")
def get_prompt(pid: str, request: Request):
    p = db.get_prompt(pid, owner_of(request))
    if not p:
        raise HTTPException(404, "not_found")
    p["versions"] = db.list_versions(pid)
    p["test_cases"] = db.list_test_cases(pid)
    p["project"] = db.get_project(p["project_id"], owner_of(request)) if p.get("project_id") else None
    p["latest_runs"] = db.list_test_runs(pid, limit=8)
    return deco(p)


@app.put("/api/prompts/{pid}")
def update_prompt(pid: str, body: PromptBody, request: Request):
    o = require_owner(request)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    p = db.update_prompt(pid, data, o)
    if not p:
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True, "prompt": deco(p)}


@app.delete("/api/prompts/{pid}")
def archive_prompt(pid: str, request: Request):
    o = require_owner(request)
    p = db.set_prompt_status(pid, "archived", o, require_owner=True)
    if not p:
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True}


@app.post("/api/prompts/{pid}/clone")
def clone_prompt(pid: str, request: Request):
    o = require_owner(request)
    p = db.clone_prompt(pid, o)
    if not p:
        raise HTTPException(404, "not_found")
    return {"ok": True, "prompt": deco(p)}


# ---- versions -----------------------------------------------------------
class VersionBody(BaseModel):
    version: str
    changelog: Optional[str] = ""


@app.get("/api/prompts/{pid}/versions")
def list_versions(pid: str):
    return {"versions": db.list_versions(pid)}


@app.post("/api/prompts/{pid}/versions")
def save_version(pid: str, body: VersionBody, request: Request):
    o = require_owner(request)
    v = db.save_version(pid, body.version, body.changelog, o)
    if v is None:
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True, "versions": v}


@app.get("/api/versions/{vid}")
def get_version(vid: str):
    v = db.get_version(vid)
    if not v:
        raise HTTPException(404, "not_found")
    return v


@app.post("/api/prompts/{pid}/versions/{vid}/restore")
def restore_version(pid: str, vid: str, request: Request):
    o = require_owner(request)
    p = db.restore_version(pid, vid, o)
    if not p:
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True, "prompt": deco(p)}


@app.get("/api/prompts/{pid}/versions/{vid}/diff")
def version_diff(pid: str, vid: str, against: Optional[str] = None):
    new = db.get_version(vid)
    if not new:
        raise HTTPException(404, "not_found")
    if against:
        old = db.get_version(against)
    else:
        vers = db.list_versions(pid)
        idx = next((i for i, x in enumerate(vers) if x["id"] == vid), None)
        old = db.get_version(vers[idx + 1]["id"]) if idx is not None and idx + 1 < len(vers) else {}
    return diffutil.diff(old or {}, new)


# ---- testing ------------------------------------------------------------
class RenderBody(BaseModel):
    variables: Optional[dict] = {}


@app.post("/api/prompts/{pid}/render")
def render_prompt(pid: str, body: RenderBody, request: Request):
    p = db.get_prompt(pid, owner_of(request))
    if not p:
        raise HTTPException(404, "not_found")
    return renderer.render_prompt(p, body.variables or {})


class TestBody(BaseModel):
    variables: Optional[dict] = {}
    model: Optional[str] = None
    models: Optional[List[str]] = None
    provider: Optional[str] = None  # legacy
    providers: Optional[List[str]] = None  # legacy
    test_case_id: Optional[str] = None
    save: Optional[bool] = True


async def _run_one(prompt, model_id, variables, test_case, owner, save):
    res = await runner.run(model_id, prompt, variables)
    # real LLM-as-judge on live runs (billed to the same wallet as the run); real
    # keyword/JSON signals on mock runs
    if res.get("live") and llm.has_key():
        ev = await evaluator.judge(res["output"], prompt, test_case)
    else:
        ev = evaluator.evaluate(res["output"], prompt, test_case)
    res["evaluation"] = ev
    if save and not res.get("error"):
        rendered = renderer.render_prompt(prompt, variables)["combined"]
        res["run_id"] = db.log_test_run(prompt["id"], {
            "prompt_version_id": None, "test_case_id": (test_case or {}).get("id"),
            "provider": res["provider"], "model": res["model"], "input_variables": variables,
            "rendered_prompt": rendered, "output": res["output"], "metrics": res["metrics"],
            "evaluation": ev, "latency_ms": res["latency_ms"], "cost_estimate": res["cost_estimate"],
            "token_estimate": res["token_estimate"]}, owner)
    return res


@app.post("/api/prompts/{pid}/test")
async def test_prompt(pid: str, body: TestBody, request: Request):
    owner = require_owner(request)  # runs cost money → require sign-in
    llm.set_relay_auth(relay_key(request))  # bill the signed-in user's own wallet
    p = db.get_prompt(pid, owner)
    if not p:
        raise HTTPException(404, "not_found")
    tc = next((t for t in db.list_test_cases(pid) if t["id"] == body.test_case_id), None) if body.test_case_id else None
    variables = body.variables or (tc or {}).get("input_variables") or {}
    model = body.model or body.provider or (p.get("model_settings") or {}).get("model") or "auto"
    return await _run_one(p, model, variables, tc, owner, body.save)


@app.post("/api/prompts/{pid}/compare")
async def compare_prompt(pid: str, body: TestBody, request: Request):
    owner = require_owner(request)
    llm.set_relay_auth(relay_key(request))
    p = db.get_prompt(pid, owner)
    if not p:
        raise HTTPException(404, "not_found")
    tc = next((t for t in db.list_test_cases(pid) if t["id"] == body.test_case_id), None) if body.test_case_id else None
    variables = body.variables or (tc or {}).get("input_variables") or {}
    models = body.models or body.providers or await llm.featured_models()
    rendered = renderer.render_prompt(p, variables)
    results = []
    for m in models:
        results.append(await _run_one(p, m, variables, tc, owner, body.save))
    return {"rendered": rendered, "results": results}


@app.get("/api/prompts/{pid}/test-runs")
def test_runs(pid: str):
    return {"runs": db.list_test_runs(pid)}


@app.get("/api/models")
async def models(request: Request):
    # Reflect the SIGNED-IN USER's billing path, not the shared owner key.
    llm.set_relay_auth(relay_key(request))
    billing = llm.billing_mode()  # "user" | "owner" | "mock"
    live = runner.REAL and billing in ("user", "owner")
    return {"models": await llm.list_models(), "featured": await llm.featured_models(),
            "live": live, "billing": billing}


# ---- deploy: serve a prompt as a live API --------------------------------
class PromptDeployBody(BaseModel):
    model: Optional[str] = None


@app.get("/api/prompts/{pid}/deployment")
def get_prompt_deployment(pid: str, request: Request):
    if not db.get_prompt(pid, owner_of(request)):
        raise HTTPException(404, "not_found")
    return {"deployment": db.get_prompt_deployment(pid)}


@app.post("/api/prompts/{pid}/deploy")
def deploy_prompt_endpoint(pid: str, body: PromptDeployBody, request: Request):
    owner = require_owner(request)
    p = db.get_prompt(pid, owner)
    if not p:
        raise HTTPException(404, "not_found")
    p.pop("badges", None)
    settings = {"prompt": p, "model": body.model or (p.get("model_settings") or {}).get("model") or "auto"}
    dep = db.deploy_prompt(pid, owner, relay_key(request), settings)
    return {"ok": True, "deployment": dep, "path": f"/api/prompt-endpoint/{dep['token']}/run"}


@app.delete("/api/prompts/{pid}/deploy")
def undeploy_prompt_endpoint(pid: str, request: Request):
    require_owner(request)
    if not db.get_prompt(pid, owner_of(request)):
        raise HTTPException(404, "not_found")
    db.undeploy_prompt(pid)
    return {"ok": True}


# Public — the unguessable token IS the credential.
@app.get("/api/prompt-endpoint/{token}")
def prompt_endpoint_info(token: str):
    dep = db.prompt_deployment_by_token(token)
    if not dep:
        raise HTTPException(404, "unknown_or_disabled_endpoint")
    s = db._pj(dep.get("settings"), {}) or {}
    p = s.get("prompt") or {}
    return {"ok": True, "prompt": p.get("name"), "variables": [v.get("name") for v in (p.get("variables") or [])],
            "calls": dep["call_count"], "usage": "POST {\"variables\": {...}} to this path + /run."}


class PromptRunBody(BaseModel):
    variables: Optional[dict] = {}


@app.post("/api/prompt-endpoint/{token}/run")
async def prompt_endpoint_run(token: str, body: PromptRunBody):
    dep = db.prompt_deployment_by_token(token)
    if not dep:
        raise HTTPException(404, "unknown_or_disabled_endpoint")
    s = db._pj(dep.get("settings"), {}) or {}
    p = s.get("prompt")
    if not p:
        raise HTTPException(404, "prompt_snapshot_missing")
    llm.set_relay_auth(dep.get("relay_key"))  # bill the deployer's own wallet
    res = await runner.run(s.get("model", "auto"), p, body.variables or {})
    db.bump_prompt_deployment(token)
    return {"output": res["output"], "model": res.get("model"), "billing": res.get("billing"),
            "metrics": res.get("metrics")}


# ---- test cases ---------------------------------------------------------
class TestCaseBody(BaseModel):
    name: str
    description: Optional[str] = ""
    input_variables: Optional[dict] = {}
    expected_keywords: Optional[list] = []
    negative_keywords: Optional[list] = []
    expected_schema: Optional[dict] = {}
    notes: Optional[str] = ""


@app.get("/api/prompts/{pid}/test-cases")
def test_cases(pid: str):
    return {"test_cases": db.list_test_cases(pid)}


@app.post("/api/prompts/{pid}/test-cases")
def create_test_case(pid: str, body: TestCaseBody, request: Request):
    o = require_owner(request)
    return {"ok": True, "test_case": db.create_test_case(pid, body.model_dump(), o)}


@app.delete("/api/test-cases/{tid}")
def delete_test_case(tid: str, request: Request):
    require_owner(request)
    db.delete_test_case(tid)
    return {"ok": True}


# ---- approvals ----------------------------------------------------------
@app.post("/api/prompts/{pid}/submit-approval")
def submit_approval(pid: str, request: Request):
    o = require_owner(request)
    if not db.submit_approval(pid, o):
        raise HTTPException(404, "not_found")
    return {"ok": True}


def require_admin(request: Request):
    o = require_owner(request)
    if not db.is_admin(o):
        raise HTTPException(403, "admin_only")
    return o


@app.get("/api/approvals")
def approvals(request: Request):
    require_admin(request)
    q = db.approval_queue()
    for a in q:
        a["badges"] = badges({"governance": a.get("governance"), "risk_level": a.get("risk_level"), "status": "pending_approval"})
    return {"approvals": q}


class ReviewBody(BaseModel):
    notes: Optional[str] = ""


@app.post("/api/approvals/{aid}/approve")
def approve(aid: str, body: ReviewBody, request: Request):
    o = require_admin(request)
    if not db.review_approval(aid, "approve", o, body.notes):
        raise HTTPException(404, "not_found")
    return {"ok": True}


@app.post("/api/approvals/{aid}/reject")
def reject(aid: str, body: ReviewBody, request: Request):
    o = require_admin(request)
    if not db.review_approval(aid, "reject", o, body.notes):
        raise HTTPException(404, "not_found")
    return {"ok": True}


@app.post("/api/approvals/{aid}/request-changes")
def request_changes(aid: str, body: ReviewBody, request: Request):
    o = require_admin(request)
    if not db.review_approval(aid, "request-changes", o, body.notes):
        raise HTTPException(404, "not_found")
    return {"ok": True}


# ---- templates ----------------------------------------------------------
@app.get("/api/templates")
def templates():
    items = db.list_templates()
    for t in items:
        t["badges"] = badges(t)
    return {"templates": items}


@app.post("/api/templates/{tid}/use")
def use_template(tid: str, request: Request, project_id: Optional[str] = None):
    o = require_owner(request)
    p = db.use_template(tid, o, project_id)
    if not p:
        raise HTTPException(404, "not_found")
    return {"ok": True, "prompt": deco(p)}


# ---- export -------------------------------------------------------------
@app.get("/api/prompts/{pid}/export/json")
def export_json(pid: str, request: Request):
    p = db.get_prompt(pid, owner_of(request))
    if not p:
        raise HTTPException(404, "not_found")
    return exporter.to_package(p, db.list_test_cases(pid))


@app.get("/api/prompts/{pid}/export/markdown")
def export_markdown(pid: str, request: Request):
    p = db.get_prompt(pid, owner_of(request))
    if not p:
        raise HTTPException(404, "not_found")
    return PlainTextResponse(exporter.to_markdown(p, db.list_test_cases(pid)))


# ---- audit --------------------------------------------------------------
@app.get("/api/prompts/{pid}/audit")
def prompt_audit(pid: str):
    return {"audit": db.audit_for(pid)}
