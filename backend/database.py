"""SQLite persistence for ZoidLab Prompter.

Postgres-portable: every JSONB column is JSON-encoded TEXT and all access goes
through these helpers, so a later swap to Postgres/SQLModel touches only this file.
Ownership = the Nyquest user id (session `sub`). Seed content (owner NULL) and
templates are visible to everyone; user content is owner-scoped.
"""
import os
import json
import uuid
import sqlite3
import datetime

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "prompter.db")


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _j(v):
    return json.dumps(v)


def _pj(v, default=None):
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


_PROMPT_JSON = ["tags", "output_schema", "variables", "model_settings", "governance"]


def init():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT, name TEXT, role TEXT DEFAULT 'user',
                org_id TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY, name TEXT, slug TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS prompt_projects (
                id TEXT PRIMARY KEY, org_id TEXT, owner_user_id TEXT,
                name TEXT NOT NULL, slug TEXT, description TEXT, status TEXT DEFAULT 'active',
                accent TEXT, icon TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS prompts (
                id TEXT PRIMARY KEY, project_id TEXT, org_id TEXT, owner_user_id TEXT,
                name TEXT NOT NULL, slug TEXT, description TEXT, category TEXT, tags TEXT,
                status TEXT DEFAULT 'draft', risk_level TEXT DEFAULT 'low', current_version TEXT DEFAULT '0.1.0',
                system_prompt TEXT, developer_prompt TEXT, user_prompt TEXT, tool_prompt TEXT,
                output_schema TEXT, variables TEXT, model_settings TEXT, governance TEXT,
                template INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_prompts_owner ON prompts(owner_user_id);
            CREATE INDEX IF NOT EXISTS idx_prompts_project ON prompts(project_id);
            CREATE TABLE IF NOT EXISTS prompt_versions (
                id TEXT PRIMARY KEY, prompt_id TEXT, version TEXT, changelog TEXT,
                system_prompt TEXT, developer_prompt TEXT, user_prompt TEXT, tool_prompt TEXT,
                output_schema TEXT, variables TEXT, model_settings TEXT, governance TEXT, status TEXT,
                created_by TEXT, created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_versions_prompt ON prompt_versions(prompt_id, created_at);
            CREATE TABLE IF NOT EXISTS prompt_test_cases (
                id TEXT PRIMARY KEY, prompt_id TEXT, name TEXT, description TEXT,
                input_variables TEXT, expected_keywords TEXT, negative_keywords TEXT,
                expected_schema TEXT, notes TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS prompt_test_runs (
                id TEXT PRIMARY KEY, prompt_id TEXT, prompt_version_id TEXT, test_case_id TEXT,
                provider TEXT, model TEXT, input_variables TEXT, rendered_prompt TEXT, output TEXT,
                metrics TEXT, evaluation TEXT, status TEXT, latency_ms INTEGER, cost_estimate REAL,
                token_estimate INTEGER, created_by TEXT, created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_runs_prompt ON prompt_test_runs(prompt_id, created_at);
            CREATE TABLE IF NOT EXISTS prompt_approvals (
                id TEXT PRIMARY KEY, prompt_id TEXT, prompt_version_id TEXT,
                submitted_by TEXT, reviewer_id TEXT, status TEXT, reviewer_notes TEXT,
                submitted_at TEXT, reviewed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, action TEXT,
                actor_user_id TEXT, details TEXT, created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id, created_at);
            CREATE TABLE IF NOT EXISTS prompt_deployments (
                id TEXT PRIMARY KEY, prompt_id TEXT UNIQUE, owner_user_id TEXT, token TEXT UNIQUE,
                relay_key TEXT, settings TEXT, enabled INTEGER DEFAULT 1, call_count INTEGER DEFAULT 0,
                last_called_at TEXT, created_at TEXT, updated_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_pdeploy_token ON prompt_deployments(token);
            """
        )
        # idempotent migration for older DBs
        cols = [r["name"] for r in c.execute("PRAGMA table_info(prompts)")]
        if "template" not in cols:
            c.execute("ALTER TABLE prompts ADD COLUMN template INTEGER DEFAULT 0")


# --- users / admin -----------------------------------------------------
def upsert_user(uid, email=None, name=None):
    if not uid:
        return
    now = now_iso()
    with _conn() as c:
        c.execute(
            """INSERT INTO users (id,email,name,role,created_at,updated_at) VALUES (?,?,?,'user',?,?)
               ON CONFLICT(id) DO UPDATE SET email=COALESCE(excluded.email,users.email),
                 name=COALESCE(excluded.name,users.name), updated_at=excluded.updated_at""",
            (uid, email, name, now, now),
        )


def is_admin(uid):
    if not uid:
        return False
    admins = [a.strip() for a in os.environ.get("PROMPTER_ADMINS", "").split(",") if a.strip()]
    if uid in admins:
        return True
    with _conn() as c:
        r = c.execute("SELECT role,email FROM users WHERE id=?", (uid,)).fetchone()
    return bool(r and (r["role"] == "admin" or (r["email"] and r["email"] in admins)))


def audit(entity_type, entity_id, action, actor, details=None):
    with _conn() as c:
        c.execute("INSERT INTO audit_logs (id,entity_type,entity_id,action,actor_user_id,details,created_at) VALUES (?,?,?,?,?,?,?)",
                  (new_id("aud"), entity_type, entity_id, action, actor, _j(details or {}), now_iso()))


def audit_for(entity_id, limit=50):
    with _conn() as c:
        rows = c.execute("SELECT * FROM audit_logs WHERE entity_id=? ORDER BY created_at DESC LIMIT ?", (entity_id, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["details"] = _pj(d.get("details"), {}); out.append(d)
    return out


# --- visibility: seed (NULL owner) + own ------------------------------
def _visible(col="owner_user_id"):
    return f"({col} IS NULL OR {col}=?)"


# --- projects ----------------------------------------------------------
def list_projects(viewer=None):
    with _conn() as c:
        rows = c.execute(
            f"""SELECT p.*, (SELECT COUNT(*) FROM prompts pr WHERE pr.project_id=p.id) AS prompt_count
                FROM prompt_projects p WHERE {_visible()} ORDER BY p.updated_at DESC""",
            (viewer,)).fetchall()
    return [dict(r) for r in rows]


def get_project(pid, viewer=None):
    with _conn() as c:
        r = c.execute(f"SELECT * FROM prompt_projects WHERE id=? AND {_visible()}", (pid, viewer)).fetchone()
    return dict(r) if r else None


def create_project(data, owner):
    pid = new_id("proj"); now = now_iso()
    with _conn() as c:
        c.execute("""INSERT INTO prompt_projects (id,owner_user_id,name,slug,description,status,accent,icon,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (pid, owner, data["name"], _slug(data.get("slug") or data["name"]), data.get("description", ""),
                   data.get("status", "active"), data.get("accent", "#7c5cfc"), data.get("icon", "◆"), now, now))
    audit("project", pid, "created", owner)
    return get_project(pid, owner)


def update_project(pid, data, owner):
    with _conn() as c:
        r = c.execute("SELECT owner_user_id FROM prompt_projects WHERE id=?", (pid,)).fetchone()
        if not r or (r["owner_user_id"] != owner and not is_admin(owner)):
            return None
        sets, args = [], []
        for k in ("name", "description", "status", "accent", "icon"):
            if k in data:
                sets.append(f"{k}=?"); args.append(data[k])
        sets.append("updated_at=?"); args.append(now_iso()); args.append(pid)
        c.execute(f"UPDATE prompt_projects SET {', '.join(sets)} WHERE id=?", args)
    return get_project(pid, owner)


def _slug(s):
    import re
    return (re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:50] or "item") + "-" + uuid.uuid4().hex[:5]


# --- prompts -----------------------------------------------------------
def _prompt_out(row, full=False):
    if not row:
        return None
    d = dict(row)
    for k in _PROMPT_JSON:
        d[k] = _pj(d.get(k), [] if k in ("tags", "variables") else {})
    d["template"] = bool(d.get("template"))
    if not full:
        for k in ("system_prompt", "developer_prompt", "user_prompt", "tool_prompt", "output_schema"):
            d.pop(k, None)
    return d


def list_prompts(viewer=None, search=None, project_id=None, category=None, status=None, risk=None, tag=None, sort="updated"):
    q = f"SELECT * FROM prompts WHERE template=0 AND {_visible()}"
    args = [viewer]
    if project_id: q += " AND project_id=?"; args.append(project_id)
    if category and category.lower() != "all": q += " AND lower(category)=lower(?)"; args.append(category)
    if status and status.lower() != "all": q += " AND status=?"; args.append(status)
    if risk and risk.lower() != "all": q += " AND risk_level=?"; args.append(risk)
    if search:
        q += " AND (lower(name) LIKE ? OR lower(description) LIKE ? OR lower(tags) LIKE ?)"
        s = f"%{search.lower()}%"; args += [s, s, s]
    if tag: q += " AND lower(tags) LIKE ?"; args.append(f'%"{tag.lower()}"%')
    order = {"newest": "created_at DESC", "updated": "updated_at DESC",
             "approved": "CASE WHEN status='approved' THEN 0 ELSE 1 END, updated_at DESC",
             "name": "name ASC"}.get(sort, "updated_at DESC")
    q += f" ORDER BY {order}"
    with _conn() as c:
        rows = c.execute(q, args).fetchall()
    out = [_prompt_out(r) for r in rows]
    if tag:
        out = [p for p in out if tag.lower() in [t.lower() for t in p.get("tags", [])]]
    return out


def get_prompt(pid, viewer=None):
    with _conn() as c:
        r = c.execute(f"SELECT * FROM prompts WHERE id=? AND {_visible()}", (pid, viewer)).fetchone()
    return _prompt_out(r, full=True)


def get_prompt_raw(pid):
    with _conn() as c:
        r = c.execute("SELECT * FROM prompts WHERE id=?", (pid,)).fetchone()
    return _prompt_out(r, full=True)


DEFAULT_MODEL_SETTINGS = {"provider": "nyquest-router", "model": "auto", "temperature": 0.4,
                          "max_tokens": 800, "top_p": 1.0, "json_mode": False, "streaming": True,
                          "tool_calling": False, "fallback_model": "openai:gpt-5", "timeout_s": 60, "retries": 0}
DEFAULT_GOVERNANCE = {"risk_level": "low", "sensitive_data": False, "pii_risk": "low",
                      "external_api": False, "requires_human_approval": False,
                      "logs_prompts": True, "logs_outputs": True, "approved_for_production": False}


def create_prompt(data, owner):
    pid = new_id("prm"); now = now_iso()
    ms = {**DEFAULT_MODEL_SETTINGS, **(data.get("model_settings") or {})}
    gov = {**DEFAULT_GOVERNANCE, **(data.get("governance") or {})}
    gov["risk_level"] = data.get("risk_level") or gov.get("risk_level", "low")
    with _conn() as c:
        c.execute(
            """INSERT INTO prompts (id,project_id,owner_user_id,name,slug,description,category,tags,status,risk_level,
                 current_version,system_prompt,developer_prompt,user_prompt,tool_prompt,output_schema,variables,
                 model_settings,governance,template,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, data.get("project_id"), owner, data["name"], _slug(data.get("slug") or data["name"]),
             data.get("description", ""), data.get("category", "General"), _j(data.get("tags", [])),
             data.get("status", "draft"), gov["risk_level"], data.get("current_version", "0.1.0"),
             data.get("system_prompt", ""), data.get("developer_prompt", ""), data.get("user_prompt", ""),
             data.get("tool_prompt", ""), _j(data.get("output_schema", {})), _j(data.get("variables", [])),
             _j(ms), _j(gov), 1 if data.get("template") else 0, now, now))
        _snapshot(c, pid, data.get("current_version", "0.1.0"), "Initial version", owner, from_prompt=True)
    audit("prompt", pid, "created", owner)
    return get_prompt(pid, owner)


def update_prompt(pid, data, owner):
    with _conn() as c:
        r = c.execute("SELECT owner_user_id,governance FROM prompts WHERE id=?", (pid,)).fetchone()
        if not r or (r["owner_user_id"] != owner and not is_admin(owner)):
            return None
        sets, args = [], []
        for k in ("name", "description", "category", "status", "risk_level", "project_id",
                  "system_prompt", "developer_prompt", "user_prompt", "tool_prompt", "current_version"):
            if k in data:
                sets.append(f"{k}=?"); args.append(data[k])
        for k in ("tags", "output_schema", "variables", "model_settings", "governance"):
            if k in data:
                sets.append(f"{k}=?"); args.append(_j(data[k]))
        # keep governance.risk_level in sync when risk_level changes
        if "risk_level" in data and "governance" not in data:
            gov = _pj(r["governance"], {}); gov["risk_level"] = data["risk_level"]
            sets.append("governance=?"); args.append(_j(gov))
        sets.append("updated_at=?"); args.append(now_iso()); args.append(pid)
        c.execute(f"UPDATE prompts SET {', '.join(sets)} WHERE id=?", args)
    audit("prompt", pid, "updated", owner)
    return get_prompt(pid, owner)


def set_prompt_status(pid, status, owner=None, require_owner=False):
    with _conn() as c:
        r = c.execute("SELECT owner_user_id FROM prompts WHERE id=?", (pid,)).fetchone()
        if not r:
            return None
        if require_owner and r["owner_user_id"] != owner and not is_admin(owner):
            return None
        c.execute("UPDATE prompts SET status=?, updated_at=? WHERE id=?", (status, now_iso(), pid))
    audit("prompt", pid, f"status:{status}", owner)
    return get_prompt_raw(pid)


def clone_prompt(pid, owner):
    src = get_prompt_raw(pid)
    if not src:
        return None
    data = {k: src.get(k) for k in ("description", "category", "tags", "system_prompt", "developer_prompt",
            "user_prompt", "tool_prompt", "output_schema", "variables", "model_settings", "governance",
            "risk_level", "project_id")}
    data["name"] = src["name"] + " (copy)"
    data["status"] = "draft"
    data["current_version"] = "0.1.0"
    if isinstance(data.get("governance"), dict):
        data["governance"] = {**data["governance"], "approved_for_production": False}
    return create_prompt(data, owner)


# --- versions ----------------------------------------------------------
def _snapshot(c, pid, version, changelog, owner, from_prompt=False, status=None):
    row = c.execute("SELECT * FROM prompts WHERE id=?", (pid,)).fetchone()
    if not row:
        return
    c.execute(
        """INSERT INTO prompt_versions (id,prompt_id,version,changelog,system_prompt,developer_prompt,user_prompt,
             tool_prompt,output_schema,variables,model_settings,governance,status,created_by,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (new_id("pv"), pid, version, changelog, row["system_prompt"], row["developer_prompt"], row["user_prompt"],
         row["tool_prompt"], row["output_schema"], row["variables"], row["model_settings"], row["governance"],
         status or row["status"], owner, now_iso()))


def save_version(pid, version, changelog, owner):
    with _conn() as c:
        r = c.execute("SELECT owner_user_id FROM prompts WHERE id=?", (pid,)).fetchone()
        if not r or (r["owner_user_id"] != owner and not is_admin(owner)):
            return None
        c.execute("UPDATE prompts SET current_version=?, updated_at=? WHERE id=?", (version, now_iso(), pid))
        _snapshot(c, pid, version, changelog or f"Saved {version}", owner)
    audit("prompt", pid, f"version:{version}", owner)
    return list_versions(pid)


def list_versions(pid):
    with _conn() as c:
        rows = c.execute("SELECT id,version,changelog,status,created_by,created_at FROM prompt_versions WHERE prompt_id=? ORDER BY created_at DESC", (pid,)).fetchall()
    return [dict(r) for r in rows]


def get_version(vid):
    with _conn() as c:
        r = c.execute("SELECT * FROM prompt_versions WHERE id=?", (vid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("output_schema", "variables", "model_settings", "governance"):
        d[k] = _pj(d.get(k), {} if k != "variables" else [])
    return d


def restore_version(pid, vid, owner):
    with _conn() as c:
        pr = c.execute("SELECT owner_user_id FROM prompts WHERE id=?", (pid,)).fetchone()
        v = c.execute("SELECT * FROM prompt_versions WHERE id=? AND prompt_id=?", (vid, pid)).fetchone()
        if not pr or not v or (pr["owner_user_id"] != owner and not is_admin(owner)):
            return None
        c.execute("""UPDATE prompts SET system_prompt=?,developer_prompt=?,user_prompt=?,tool_prompt=?,
                     output_schema=?,variables=?,model_settings=?,governance=?,current_version=?,updated_at=? WHERE id=?""",
                  (v["system_prompt"], v["developer_prompt"], v["user_prompt"], v["tool_prompt"], v["output_schema"],
                   v["variables"], v["model_settings"], v["governance"], v["version"], now_iso(), pid))
        _snapshot(c, pid, v["version"], f"Restored from {v['created_at'][:16].replace('T', ' ')}", owner)
    audit("prompt", pid, f"restore:{v['version']}", owner)
    return get_prompt(pid, owner)


# --- test cases / runs -------------------------------------------------
def list_test_cases(pid):
    with _conn() as c:
        rows = c.execute("SELECT * FROM prompt_test_cases WHERE prompt_id=? ORDER BY created_at", (pid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("input_variables", "expected_schema"):
            d[k] = _pj(d.get(k), {})
        for k in ("expected_keywords", "negative_keywords"):
            d[k] = _pj(d.get(k), [])
        out.append(d)
    return out


def create_test_case(pid, data, owner):
    tid = new_id("tc"); now = now_iso()
    with _conn() as c:
        c.execute("""INSERT INTO prompt_test_cases (id,prompt_id,name,description,input_variables,expected_keywords,
                     negative_keywords,expected_schema,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (tid, pid, data.get("name", "Test case"), data.get("description", ""),
                   _j(data.get("input_variables", {})), _j(data.get("expected_keywords", [])),
                   _j(data.get("negative_keywords", [])), _j(data.get("expected_schema", {})),
                   data.get("notes", ""), now, now))
    return [t for t in list_test_cases(pid) if t["id"] == tid][0]


def delete_test_case(tid):
    with _conn() as c:
        c.execute("DELETE FROM prompt_test_cases WHERE id=?", (tid,))


def log_test_run(pid, data, owner):
    rid = new_id("tr")
    with _conn() as c:
        c.execute("""INSERT INTO prompt_test_runs (id,prompt_id,prompt_version_id,test_case_id,provider,model,
                     input_variables,rendered_prompt,output,metrics,evaluation,status,latency_ms,cost_estimate,
                     token_estimate,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (rid, pid, data.get("prompt_version_id"), data.get("test_case_id"), data.get("provider"),
                   data.get("model"), _j(data.get("input_variables", {})), data.get("rendered_prompt", ""),
                   data.get("output", ""), _j(data.get("metrics", {})), _j(data.get("evaluation", {})),
                   data.get("status", "complete"), data.get("latency_ms"), data.get("cost_estimate"),
                   data.get("token_estimate"), owner, now_iso()))
    return rid


def list_test_runs(pid, limit=50):
    with _conn() as c:
        rows = c.execute("SELECT * FROM prompt_test_runs WHERE prompt_id=? ORDER BY created_at DESC LIMIT ?", (pid, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("input_variables", "metrics", "evaluation"):
            d[k] = _pj(d.get(k), {})
        out.append(d)
    return out


# --- approvals ---------------------------------------------------------
def submit_approval(pid, owner):
    p = get_prompt_raw(pid)
    if not p:
        return None
    with _conn() as c:
        c.execute("DELETE FROM prompt_approvals WHERE prompt_id=? AND status='pending'", (pid,))
        c.execute("""INSERT INTO prompt_approvals (id,prompt_id,prompt_version_id,submitted_by,status,submitted_at)
                     VALUES (?,?,?,?,'pending',?)""",
                  (new_id("appr"), pid, p.get("current_version"), owner, now_iso()))
    set_prompt_status(pid, "pending_approval")
    audit("prompt", pid, "submitted_for_approval", owner)
    return True


def approval_queue():
    with _conn() as c:
        rows = c.execute("""SELECT a.*, p.name AS prompt_name, p.slug AS prompt_slug, p.category, p.risk_level,
                            p.description, p.governance FROM prompt_approvals a JOIN prompts p ON p.id=a.prompt_id
                            WHERE a.status='pending' ORDER BY a.submitted_at DESC""").fetchall()
    out = []
    for r in rows:
        d = dict(r); d["governance"] = _pj(d.get("governance"), {}); out.append(d)
    return out


def review_approval(aid, decision, reviewer, notes=""):
    status_map = {"approve": "approved", "reject": "rejected", "request-changes": "changes_requested"}
    prompt_status = {"approve": "approved", "reject": "draft", "request-changes": "draft"}
    st = status_map.get(decision)
    if not st:
        return None
    with _conn() as c:
        a = c.execute("SELECT prompt_id FROM prompt_approvals WHERE id=?", (aid,)).fetchone()
        if not a:
            return None
        c.execute("UPDATE prompt_approvals SET status=?,reviewer_id=?,reviewer_notes=?,reviewed_at=? WHERE id=?",
                  (st, reviewer, notes, now_iso(), aid))
        pid = a["prompt_id"]
    set_prompt_status(pid, prompt_status[decision])
    if decision == "approve":
        p = get_prompt_raw(pid)
        gov = p.get("governance") or {}; gov["approved_for_production"] = True
        update_prompt(pid, {"governance": gov}, p.get("owner_user_id"))
    audit("prompt", pid, f"approval:{st}", reviewer, {"notes": notes})
    return True


# --- dashboard stats ---------------------------------------------------
def stats(viewer=None):
    with _conn() as c:
        def n(where, args):
            return c.execute(f"SELECT COUNT(*) c FROM prompts WHERE template=0 AND {_visible()} {where}", [viewer] + args).fetchone()["c"]
        total = n("", [])
        approved = n("AND status IN ('approved','deployed')", [])
        draft = n("AND status='draft'", [])
        runs = c.execute(f"""SELECT COUNT(*) c FROM prompt_test_runs r JOIN prompts p ON p.id=r.prompt_id
                            WHERE {_visible('p.owner_user_id')}""", (viewer,)).fetchone()["c"]
        avg = c.execute(f"""SELECT AVG(r.cost_estimate) cost, AVG(r.latency_ms) lat FROM prompt_test_runs r
                           JOIN prompts p ON p.id=r.prompt_id WHERE {_visible('p.owner_user_id')}""", (viewer,)).fetchone()
    return {"total": total, "approved": approved, "draft": draft, "test_runs": runs,
            "avg_cost": round(avg["cost"] or 0, 5), "avg_latency": int(avg["lat"] or 0)}


# --- templates ---------------------------------------------------------
def list_templates():
    with _conn() as c:
        rows = c.execute("SELECT * FROM prompts WHERE template=1 ORDER BY name").fetchall()
    return [_prompt_out(r, full=True) for r in rows]


def get_template(tid):
    with _conn() as c:
        r = c.execute("SELECT * FROM prompts WHERE id=? AND template=1", (tid,)).fetchone()
    return _prompt_out(r, full=True)


def use_template(tid, owner, project_id=None):
    t = get_template(tid)
    if not t:
        return None
    data = {k: t.get(k) for k in ("description", "category", "tags", "system_prompt", "developer_prompt",
            "user_prompt", "tool_prompt", "output_schema", "variables", "model_settings", "governance", "risk_level")}
    data["name"] = t["name"].replace(" Prompt", "")
    data["project_id"] = project_id
    data["status"] = "draft"
    p = create_prompt(data, owner)
    # copy the template's test cases onto the new prompt
    for tc in list_test_cases(t["id"]):
        create_test_case(p["id"], tc, owner)
    return p


def counts_by(field, viewer=None):
    """Distinct value counts for a prompt column (category/status/risk_level) — for filters."""
    with _conn() as c:
        rows = c.execute(f"SELECT {field} v, COUNT(*) c FROM prompts WHERE template=0 AND {_visible()} GROUP BY {field}", (viewer,)).fetchall()
    return [{"name": r["v"], "count": r["c"]} for r in rows if r["v"]]


# --- deployments (prompt served as a live API) -------------------------
def _pdeployment_out(r):
    if not r:
        return None
    d = dict(r)
    d["settings"] = _pj(d.get("settings"), {})
    d["enabled"] = bool(d["enabled"])
    d.pop("relay_key", None)
    return d


def deploy_prompt(pid, owner, relay_key, settings):
    now = now_iso()
    with _conn() as c:
        ex = c.execute("SELECT id, token FROM prompt_deployments WHERE prompt_id=?", (pid,)).fetchone()
        token = ex["token"] if ex else uuid.uuid4().hex
        if ex:
            c.execute("UPDATE prompt_deployments SET owner_user_id=?, relay_key=?, settings=?, enabled=1, updated_at=? WHERE id=?",
                      (owner, relay_key, _j(settings), now, ex["id"]))
        else:
            c.execute("""INSERT INTO prompt_deployments (id,prompt_id,owner_user_id,token,relay_key,settings,enabled,call_count,created_at,updated_at)
                         VALUES (?,?,?,?,?,?,1,0,?,?)""", (new_id("dep"), pid, owner, token, relay_key, _j(settings), now, now))
    return get_prompt_deployment(pid)


def get_prompt_deployment(pid):
    with _conn() as c:
        r = c.execute("SELECT * FROM prompt_deployments WHERE prompt_id=?", (pid,)).fetchone()
    out = _pdeployment_out(r)
    if out:
        out["token"] = r["token"]
    return out


def prompt_deployment_by_token(token):
    with _conn() as c:
        r = c.execute("SELECT * FROM prompt_deployments WHERE token=? AND enabled=1", (token,)).fetchone()
    return dict(r) if r else None


def undeploy_prompt(pid):
    with _conn() as c:
        c.execute("UPDATE prompt_deployments SET enabled=0, updated_at=? WHERE prompt_id=?", (now_iso(), pid))
    return True


def bump_prompt_deployment(token):
    with _conn() as c:
        c.execute("UPDATE prompt_deployments SET call_count=call_count+1, last_called_at=? WHERE token=?", (now_iso(), token))
