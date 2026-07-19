"""Postgres data layer for ZoidLab Prompter with per-tenant Row-Level Security (§3.2).

Tenant isolation is enforced by the database, not just the app: prompt_projects, prompts
and prompt_deployments carry owner_user_id, have FORCE ROW LEVEL SECURITY, and a policy
exposing only rows whose owner matches `app.current_owner` (set per transaction) or is
NULL (shared seed / templates). Child tables (versions, test cases, test runs, approvals,
audit logs) have no owner column — they are reached only through an RLS-protected prompt —
so they carry no policy, matching the former sqlite scoping. Engine-internal paths (owner
checks before guarded writes, the approval queue, and the deployed prompt-as-API token
endpoint where the unguessable token IS the credential) go through admin_conn(), exactly
mirroring the unfiltered reads the sqlite layer performed. Public API mirrors the former
sqlite database.py exactly.
"""
import os
import json
import uuid
import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# App connections use the RLS-enforced role (app_rls); DDL + cross-tenant admin use the
# superuser (foundry), which bypasses RLS by design.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://app_rls@127.0.0.1:5433/prompter")
DATABASE_URL_ADMIN = os.environ.get("DATABASE_URL_ADMIN", "postgresql://foundry@127.0.0.1:5433/prompter")
_pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=True, kwargs={"autocommit": False})


def admin_conn():
    return psycopg.connect(DATABASE_URL_ADMIN, row_factory=dict_row)


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _j(v):
    return json.dumps(v)


def _pj(v, default=None):
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


def _slug(s):
    import re
    return (re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:50] or "item") + "-" + uuid.uuid4().hex[:5]


class _tx:
    """Transaction scoped to a tenant: sets app.current_owner so RLS applies."""
    def __init__(self, owner):
        self.owner = owner or ""

    def __enter__(self):
        self.conn = _pool.getconn()
        self.cur = self.conn.cursor(row_factory=dict_row)
        self.cur.execute("SELECT set_config('app.current_owner', %s, true)", (self.owner,))
        return self.cur

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.cur.close()
            _pool.putconn(self.conn)


_PROMPT_JSON = ["tags", "output_schema", "variables", "model_settings", "governance"]
_TENANT_TABLES = ["prompt_projects", "prompts", "prompt_deployments"]


def init():
    with admin_conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT, name TEXT, role TEXT DEFAULT 'user',
            org_id TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY, name TEXT, slug TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS prompt_projects (
            id TEXT PRIMARY KEY, org_id TEXT, owner_user_id TEXT,
            name TEXT NOT NULL, slug TEXT, description TEXT, status TEXT DEFAULT 'active',
            accent TEXT, icon TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS prompts (
            id TEXT PRIMARY KEY, project_id TEXT, org_id TEXT, owner_user_id TEXT,
            name TEXT NOT NULL, slug TEXT, description TEXT, category TEXT, tags TEXT,
            status TEXT DEFAULT 'draft', risk_level TEXT DEFAULT 'low', current_version TEXT DEFAULT '0.1.0',
            system_prompt TEXT, developer_prompt TEXT, user_prompt TEXT, tool_prompt TEXT,
            output_schema TEXT, variables TEXT, model_settings TEXT, governance TEXT,
            template INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)""")
        c.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS template INTEGER DEFAULT 0")
        c.execute("CREATE INDEX IF NOT EXISTS idx_prompts_owner ON prompts(owner_user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_prompts_project ON prompts(project_id)")
        c.execute("""CREATE TABLE IF NOT EXISTS prompt_versions (
            id TEXT PRIMARY KEY, prompt_id TEXT, version TEXT, changelog TEXT,
            system_prompt TEXT, developer_prompt TEXT, user_prompt TEXT, tool_prompt TEXT,
            output_schema TEXT, variables TEXT, model_settings TEXT, governance TEXT, status TEXT,
            created_by TEXT, created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_versions_prompt ON prompt_versions(prompt_id, created_at)")
        c.execute("""CREATE TABLE IF NOT EXISTS prompt_test_cases (
            id TEXT PRIMARY KEY, prompt_id TEXT, name TEXT, description TEXT,
            input_variables TEXT, expected_keywords TEXT, negative_keywords TEXT,
            expected_schema TEXT, notes TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS prompt_test_runs (
            id TEXT PRIMARY KEY, prompt_id TEXT, prompt_version_id TEXT, test_case_id TEXT,
            provider TEXT, model TEXT, input_variables TEXT, rendered_prompt TEXT, output TEXT,
            metrics TEXT, evaluation TEXT, status TEXT, latency_ms INTEGER, cost_estimate DOUBLE PRECISION,
            token_estimate INTEGER, created_by TEXT, created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_runs_prompt ON prompt_test_runs(prompt_id, created_at)")
        c.execute("""CREATE TABLE IF NOT EXISTS prompt_approvals (
            id TEXT PRIMARY KEY, prompt_id TEXT, prompt_version_id TEXT,
            submitted_by TEXT, reviewer_id TEXT, status TEXT, reviewer_notes TEXT,
            submitted_at TEXT, reviewed_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, action TEXT,
            actor_user_id TEXT, details TEXT, created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id, created_at)")
        c.execute("""CREATE TABLE IF NOT EXISTS prompt_deployments (
            id TEXT PRIMARY KEY, prompt_id TEXT UNIQUE, owner_user_id TEXT, token TEXT UNIQUE,
            relay_key TEXT, settings TEXT, enabled INTEGER DEFAULT 1, call_count INTEGER DEFAULT 0,
            last_called_at TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pdeploy_token ON prompt_deployments(token)")
        for t in _TENANT_TABLES:
            c.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            c.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            c.execute(f"DROP POLICY IF EXISTS {t}_isolation ON {t}")
            c.execute(f"""CREATE POLICY {t}_isolation ON {t}
                USING (owner_user_id IS NULL OR owner_user_id = current_setting('app.current_owner', true))
                WITH CHECK (owner_user_id IS NULL OR owner_user_id = current_setting('app.current_owner', true))""")
        c.execute("GRANT USAGE ON SCHEMA public TO app_rls")
        c.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_rls")


# --- users / admin -----------------------------------------------------
def upsert_user(uid, email=None, name=None):
    if not uid:
        return
    now = now_iso()
    with _tx(uid) as cur:
        cur.execute(
            """INSERT INTO users (id,email,name,role,created_at,updated_at) VALUES (%s,%s,%s,'user',%s,%s)
               ON CONFLICT (id) DO UPDATE SET email=COALESCE(EXCLUDED.email,users.email),
                 name=COALESCE(EXCLUDED.name,users.name), updated_at=EXCLUDED.updated_at""",
            (uid, email, name, now, now),
        )


def is_admin(uid):
    if not uid:
        return False
    admins = [a.strip() for a in os.environ.get("PROMPTER_ADMINS", "").split(",") if a.strip()]
    if uid in admins:
        return True
    with _tx(uid) as cur:
        cur.execute("SELECT role,email FROM users WHERE id=%s", (uid,))
        r = cur.fetchone()
    return bool(r and (r["role"] == "admin" or (r["email"] and r["email"] in admins)))


def audit(entity_type, entity_id, action, actor, details=None):
    with _tx(None) as cur:
        cur.execute("INSERT INTO audit_logs (id,entity_type,entity_id,action,actor_user_id,details,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (new_id("aud"), entity_type, entity_id, action, actor, _j(details or {}), now_iso()))


def audit_for(entity_id, limit=50):
    with _tx(None) as cur:
        cur.execute("SELECT * FROM audit_logs WHERE entity_id=%s ORDER BY created_at DESC LIMIT %s", (entity_id, limit))
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r); d["details"] = _pj(d.get("details"), {}); out.append(d)
    return out


# --- projects ----------------------------------------------------------
def list_projects(viewer=None):
    # RLS replaces the old owner-filter WHERE clause
    with _tx(viewer) as cur:
        cur.execute("""SELECT p.*, (SELECT COUNT(*) FROM prompts pr WHERE pr.project_id=p.id) AS prompt_count
                       FROM prompt_projects p ORDER BY p.updated_at DESC""")
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_project(pid, viewer=None):
    with _tx(viewer) as cur:
        cur.execute("SELECT * FROM prompt_projects WHERE id=%s", (pid,))
        r = cur.fetchone()
    return dict(r) if r else None


def create_project(data, owner):
    pid = new_id("proj"); now = now_iso()
    with _tx(owner) as cur:
        cur.execute("""INSERT INTO prompt_projects (id,owner_user_id,name,slug,description,status,accent,icon,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (pid, owner, data["name"], _slug(data.get("slug") or data["name"]), data.get("description", ""),
                     data.get("status", "active"), data.get("accent", "#7c5cfc"), data.get("icon", "◆"), now, now))
    audit("project", pid, "created", owner)
    return get_project(pid, owner)


def update_project(pid, data, owner):
    # explicit owner/admin check guards the write (admin path must see the row past RLS)
    with admin_conn() as c:
        r = c.execute("SELECT owner_user_id FROM prompt_projects WHERE id=%s", (pid,)).fetchone()
        if not r or (r["owner_user_id"] != owner and not is_admin(owner)):
            return None
        sets, args = [], []
        for k in ("name", "description", "status", "accent", "icon"):
            if k in data:
                sets.append(f"{k}=%s"); args.append(data[k])
        sets.append("updated_at=%s"); args.append(now_iso()); args.append(pid)
        c.execute(f"UPDATE prompt_projects SET {', '.join(sets)} WHERE id=%s", args)
        c.commit()
    return get_project(pid, owner)


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
    q = "SELECT * FROM prompts WHERE template=0"
    args = []
    if project_id: q += " AND project_id=%s"; args.append(project_id)
    if category and category.lower() != "all": q += " AND lower(category)=lower(%s)"; args.append(category)
    if status and status.lower() != "all": q += " AND status=%s"; args.append(status)
    if risk and risk.lower() != "all": q += " AND risk_level=%s"; args.append(risk)
    if search:
        q += " AND (lower(name) LIKE %s OR lower(description) LIKE %s OR lower(tags) LIKE %s)"
        s = f"%{search.lower()}%"; args += [s, s, s]
    if tag: q += " AND lower(tags) LIKE %s"; args.append(f'%"{tag.lower()}"%')
    order = {"newest": "created_at DESC", "updated": "updated_at DESC",
             "approved": "CASE WHEN status='approved' THEN 0 ELSE 1 END, updated_at DESC",
             "name": "name ASC"}.get(sort, "updated_at DESC")
    q += f" ORDER BY {order}"
    with _tx(viewer) as cur:
        cur.execute(q, args)
        rows = cur.fetchall()
    out = [_prompt_out(r) for r in rows]
    if tag:
        out = [p for p in out if tag.lower() in [t.lower() for t in p.get("tags", [])]]
    return out


def get_prompt(pid, viewer=None):
    with _tx(viewer) as cur:
        cur.execute("SELECT * FROM prompts WHERE id=%s", (pid,))
        r = cur.fetchone()
    return _prompt_out(r, full=True)


def get_prompt_raw(pid):
    # engine-internal unfiltered read (sqlite read with no owner filter) — bypasses RLS
    with admin_conn() as c:
        r = c.execute("SELECT * FROM prompts WHERE id=%s", (pid,)).fetchone()
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
    with _tx(owner) as cur:
        cur.execute(
            """INSERT INTO prompts (id,project_id,owner_user_id,name,slug,description,category,tags,status,risk_level,
                 current_version,system_prompt,developer_prompt,user_prompt,tool_prompt,output_schema,variables,
                 model_settings,governance,template,created_at,updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (pid, data.get("project_id"), owner, data["name"], _slug(data.get("slug") or data["name"]),
             data.get("description", ""), data.get("category", "General"), _j(data.get("tags", [])),
             data.get("status", "draft"), gov["risk_level"], data.get("current_version", "0.1.0"),
             data.get("system_prompt", ""), data.get("developer_prompt", ""), data.get("user_prompt", ""),
             data.get("tool_prompt", ""), _j(data.get("output_schema", {})), _j(data.get("variables", [])),
             _j(ms), _j(gov), 1 if data.get("template") else 0, now, now))
        _snapshot(cur, pid, data.get("current_version", "0.1.0"), "Initial version", owner, from_prompt=True)
    audit("prompt", pid, "created", owner)
    return get_prompt(pid, owner)


def update_prompt(pid, data, owner):
    with admin_conn() as c:
        r = c.execute("SELECT owner_user_id,governance FROM prompts WHERE id=%s", (pid,)).fetchone()
        if not r or (r["owner_user_id"] != owner and not is_admin(owner)):
            return None
        sets, args = [], []
        for k in ("name", "description", "category", "status", "risk_level", "project_id",
                  "system_prompt", "developer_prompt", "user_prompt", "tool_prompt", "current_version"):
            if k in data:
                sets.append(f"{k}=%s"); args.append(data[k])
        for k in ("tags", "output_schema", "variables", "model_settings", "governance"):
            if k in data:
                sets.append(f"{k}=%s"); args.append(_j(data[k]))
        # keep governance.risk_level in sync when risk_level changes
        if "risk_level" in data and "governance" not in data:
            gov = _pj(r["governance"], {}); gov["risk_level"] = data["risk_level"]
            sets.append("governance=%s"); args.append(_j(gov))
        sets.append("updated_at=%s"); args.append(now_iso()); args.append(pid)
        c.execute(f"UPDATE prompts SET {', '.join(sets)} WHERE id=%s", args)
        c.commit()
    audit("prompt", pid, "updated", owner)
    return get_prompt(pid, owner)


def set_prompt_status(pid, status, owner=None, require_owner=False):
    with admin_conn() as c:
        r = c.execute("SELECT owner_user_id FROM prompts WHERE id=%s", (pid,)).fetchone()
        if not r:
            return None
        if require_owner and r["owner_user_id"] != owner and not is_admin(owner):
            return None
        c.execute("UPDATE prompts SET status=%s, updated_at=%s WHERE id=%s", (status, now_iso(), pid))
        c.commit()
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
    # works with either a _tx cursor or an admin connection (both dict_row)
    r = c.execute("SELECT * FROM prompts WHERE id=%s", (pid,)).fetchone()
    if not r:
        return
    c.execute(
        """INSERT INTO prompt_versions (id,prompt_id,version,changelog,system_prompt,developer_prompt,user_prompt,
             tool_prompt,output_schema,variables,model_settings,governance,status,created_by,created_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (new_id("pv"), pid, version, changelog, r["system_prompt"], r["developer_prompt"], r["user_prompt"],
         r["tool_prompt"], r["output_schema"], r["variables"], r["model_settings"], r["governance"],
         status or r["status"], owner, now_iso()))


def save_version(pid, version, changelog, owner):
    with admin_conn() as c:
        r = c.execute("SELECT owner_user_id FROM prompts WHERE id=%s", (pid,)).fetchone()
        if not r or (r["owner_user_id"] != owner and not is_admin(owner)):
            return None
        c.execute("UPDATE prompts SET current_version=%s, updated_at=%s WHERE id=%s", (version, now_iso(), pid))
        _snapshot(c, pid, version, changelog or f"Saved {version}", owner)
        c.commit()
    audit("prompt", pid, f"version:{version}", owner)
    return list_versions(pid)


def list_versions(pid):
    with _tx(None) as cur:
        cur.execute("SELECT id,version,changelog,status,created_by,created_at FROM prompt_versions WHERE prompt_id=%s ORDER BY created_at DESC", (pid,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_version(vid):
    with _tx(None) as cur:
        cur.execute("SELECT * FROM prompt_versions WHERE id=%s", (vid,))
        r = cur.fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("output_schema", "variables", "model_settings", "governance"):
        d[k] = _pj(d.get(k), {} if k != "variables" else [])
    return d


def restore_version(pid, vid, owner):
    with admin_conn() as c:
        pr = c.execute("SELECT owner_user_id FROM prompts WHERE id=%s", (pid,)).fetchone()
        v = c.execute("SELECT * FROM prompt_versions WHERE id=%s AND prompt_id=%s", (vid, pid)).fetchone()
        if not pr or not v or (pr["owner_user_id"] != owner and not is_admin(owner)):
            return None
        c.execute("""UPDATE prompts SET system_prompt=%s,developer_prompt=%s,user_prompt=%s,tool_prompt=%s,
                     output_schema=%s,variables=%s,model_settings=%s,governance=%s,current_version=%s,updated_at=%s WHERE id=%s""",
                  (v["system_prompt"], v["developer_prompt"], v["user_prompt"], v["tool_prompt"], v["output_schema"],
                   v["variables"], v["model_settings"], v["governance"], v["version"], now_iso(), pid))
        _snapshot(c, pid, v["version"], f"Restored from {v['created_at'][:16].replace('T', ' ')}", owner)
        c.commit()
    audit("prompt", pid, f"restore:{v['version']}", owner)
    return get_prompt(pid, owner)


# --- test cases / runs -------------------------------------------------
def list_test_cases(pid):
    with _tx(None) as cur:
        cur.execute("SELECT * FROM prompt_test_cases WHERE prompt_id=%s ORDER BY created_at", (pid,))
        rows = cur.fetchall()
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
    with _tx(None) as cur:
        cur.execute("""INSERT INTO prompt_test_cases (id,prompt_id,name,description,input_variables,expected_keywords,
                       negative_keywords,expected_schema,notes,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (tid, pid, data.get("name", "Test case"), data.get("description", ""),
                     _j(data.get("input_variables", {})), _j(data.get("expected_keywords", [])),
                     _j(data.get("negative_keywords", [])), _j(data.get("expected_schema", {})),
                     data.get("notes", ""), now, now))
    return [t for t in list_test_cases(pid) if t["id"] == tid][0]


def delete_test_case(tid):
    with _tx(None) as cur:
        cur.execute("DELETE FROM prompt_test_cases WHERE id=%s", (tid,))


def log_test_run(pid, data, owner):
    rid = new_id("tr")
    with _tx(None) as cur:
        cur.execute("""INSERT INTO prompt_test_runs (id,prompt_id,prompt_version_id,test_case_id,provider,model,
                       input_variables,rendered_prompt,output,metrics,evaluation,status,latency_ms,cost_estimate,
                       token_estimate,created_by,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (rid, pid, data.get("prompt_version_id"), data.get("test_case_id"), data.get("provider"),
                     data.get("model"), _j(data.get("input_variables", {})), data.get("rendered_prompt", ""),
                     data.get("output", ""), _j(data.get("metrics", {})), _j(data.get("evaluation", {})),
                     data.get("status", "complete"), data.get("latency_ms"), data.get("cost_estimate"),
                     data.get("token_estimate"), owner, now_iso()))
    return rid


def list_test_runs(pid, limit=50):
    with _tx(None) as cur:
        cur.execute("SELECT * FROM prompt_test_runs WHERE prompt_id=%s ORDER BY created_at DESC LIMIT %s", (pid, limit))
        rows = cur.fetchall()
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
    with _tx(None) as cur:
        cur.execute("DELETE FROM prompt_approvals WHERE prompt_id=%s AND status='pending'", (pid,))
        cur.execute("""INSERT INTO prompt_approvals (id,prompt_id,prompt_version_id,submitted_by,status,submitted_at)
                       VALUES (%s,%s,%s,%s,'pending',%s)""",
                    (new_id("appr"), pid, p.get("current_version"), owner, now_iso()))
    set_prompt_status(pid, "pending_approval")
    audit("prompt", pid, "submitted_for_approval", owner)
    return True


def approval_queue():
    # reviewer view across all tenants (sqlite showed all pending) — admin read past RLS
    with admin_conn() as c:
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
    with admin_conn() as c:
        a = c.execute("SELECT prompt_id FROM prompt_approvals WHERE id=%s", (aid,)).fetchone()
        if not a:
            return None
        c.execute("UPDATE prompt_approvals SET status=%s,reviewer_id=%s,reviewer_notes=%s,reviewed_at=%s WHERE id=%s",
                  (st, reviewer, notes, now_iso(), aid))
        c.commit()
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
    with _tx(viewer) as cur:
        def n(where):
            cur.execute(f"SELECT COUNT(*) c FROM prompts WHERE template=0 {where}")
            return int(cur.fetchone()["c"])
        total = n("")
        approved = n("AND status IN ('approved','deployed')")
        draft = n("AND status='draft'")
        # RLS on prompts scopes the joins that _visible() used to scope
        cur.execute("SELECT COUNT(*) c FROM prompt_test_runs r JOIN prompts p ON p.id=r.prompt_id")
        runs = int(cur.fetchone()["c"])
        cur.execute("""SELECT AVG(r.cost_estimate) cost, AVG(r.latency_ms) lat FROM prompt_test_runs r
                       JOIN prompts p ON p.id=r.prompt_id""")
        avg = cur.fetchone()
    return {"total": total, "approved": approved, "draft": draft, "test_runs": runs,
            "avg_cost": round(float(avg["cost"] or 0), 5), "avg_latency": int(float(avg["lat"] or 0))}


# --- templates ---------------------------------------------------------
def list_templates():
    # sqlite exposed all templates to everyone regardless of owner — admin read preserves that
    with admin_conn() as c:
        rows = c.execute("SELECT * FROM prompts WHERE template=1 ORDER BY name").fetchall()
    return [_prompt_out(r, full=True) for r in rows]


def get_template(tid):
    with admin_conn() as c:
        r = c.execute("SELECT * FROM prompts WHERE id=%s AND template=1", (tid,)).fetchone()
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
    with _tx(viewer) as cur:
        cur.execute(f"SELECT {field} v, COUNT(*) c FROM prompts WHERE template=0 GROUP BY {field}")
        rows = cur.fetchall()
    return [{"name": r["v"], "count": int(r["c"])} for r in rows if r["v"]]


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
    # route already verified prompt ownership via get_prompt(pid, owner); admin write
    # mirrors the sqlite unfiltered upsert (reuses the existing token on redeploy)
    now = now_iso()
    with admin_conn() as c:
        ex = c.execute("SELECT id, token FROM prompt_deployments WHERE prompt_id=%s", (pid,)).fetchone()
        token = ex["token"] if ex else uuid.uuid4().hex
        if ex:
            c.execute("UPDATE prompt_deployments SET owner_user_id=%s, relay_key=%s, settings=%s, enabled=1, updated_at=%s WHERE id=%s",
                      (owner, relay_key, _j(settings), now, ex["id"]))
        else:
            c.execute("""INSERT INTO prompt_deployments (id,prompt_id,owner_user_id,token,relay_key,settings,enabled,call_count,created_at,updated_at)
                         VALUES (%s,%s,%s,%s,%s,%s,1,0,%s,%s)""", (new_id("dep"), pid, owner, token, relay_key, _j(settings), now, now))
        c.commit()
    return get_prompt_deployment(pid)


def get_prompt_deployment(pid):
    # callers gate on get_prompt(pid, owner) first; sqlite read was unfiltered
    with admin_conn() as c:
        r = c.execute("SELECT * FROM prompt_deployments WHERE prompt_id=%s", (pid,)).fetchone()
    out = _pdeployment_out(r)
    if out:
        out["token"] = r["token"]
    return out


def prompt_deployment_by_token(token):
    # public prompt-as-API path: no session — the unguessable token IS the credential,
    # so resolve it past RLS (returns relay_key + snapshotted settings for the runner)
    with admin_conn() as c:
        r = c.execute("SELECT * FROM prompt_deployments WHERE token=%s AND enabled=1", (token,)).fetchone()
    return dict(r) if r else None


def undeploy_prompt(pid):
    with admin_conn() as c:
        c.execute("UPDATE prompt_deployments SET enabled=0, updated_at=%s WHERE prompt_id=%s", (now_iso(), pid))
        c.commit()
    return True


def bump_prompt_deployment(token):
    with admin_conn() as c:
        c.execute("UPDATE prompt_deployments SET call_count=call_count+1, last_called_at=%s WHERE token=%s", (now_iso(), token))
        c.commit()
