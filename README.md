# ZoidLab Prompter

**Part of the [ZoidLab platform](https://github.com/Zoidlab-Foundry-m/zoidlab-foundry) · Live at [prompter.zoidlab.ai](https://prompter.zoidlab.ai)**

**Design, test, version, and deploy production prompts.** — *GitHub for enterprise AI prompts.*

Prompter is Nyquest's prompt lifecycle control plane: manage prompts like software —
versioned, tested, approved, deployed, monitored, and reusable across Nyquest agents,
workflows, and customer deployments.

> **Access — Nyquest Pro.** Prompter is a Pro workspace: sign in with your Nyquest account
> (a **Pro or Teams** plan is required; the whole app is gated). Model runs route through **your
> own Nyquest models and bill your own wallet** — and you pick which model to test and compare.
> One `.zoidlab.ai` session is shared across every ZoidLab app.

## The core workflow

**Project → Prompt → Variables → Test → Compare → Version → Approve → Export / Deploy**

- **Prompt editor** — system / developer / user / tool sections, `{{variables}}`, output schema,
  live render, inline test runner, unsaved-changes indicator.
- **Test Lab** — run a prompt across mock providers (OpenAI, Claude, Gemini, Llama, Mistral,
  Nyquest Router) and compare output, cost, latency, tokens, quality, and risk side by side.
- **Versioning** — immutable versions, changelogs, side-by-side diff, one-click rollback.
- **Governance** — risk level, PII risk, human-approval and logging flags, visible badges.
- **Approval queue** — submit for review; reviewers approve / reject / request changes.
- **Export** — the **Nyquest Prompt Package** (`prompt.package.json`) + Markdown.

## Stack

Aligned to the ZoidLab platform standard (same as Builder / Marketplace / Foundry):

- **Frontend** — Next.js 15, React 19, TypeScript, TailwindCSS (dark by default)
- **Backend** — FastAPI (Python), SQLite (Postgres-portable — all access behind `database.py`;
  JSONB columns stored as JSON text)
- **Auth** — shared ZoidLab / Nyquest SSO cookie (`zb_session`)
- **Deploy** — systemd + Cloudflare Tunnel (`prompter-api` :8400, `prompter-web` :3400)

## Quick start (local)

```bash
cp .env.example .env          # set BUILDER_SESSION_SECRET

cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8400   # seeds 10 templates + example projects on first boot

cd ../frontend
npm install
npm run dev                    # http://localhost:3400
```

Or with Docker: `docker compose up --build` (frontend :3400, backend :8400, SQLite volume).

## Environment

| Var | Purpose |
|-----|---------|
| `BUILDER_SESSION_SECRET` | Shared SSO secret — must match the other *.zoidlab.ai apps |
| `PROMPTER_API_URL` | Backend URL the frontend proxies `/api/*` to |
| `ENABLE_MOCK_MODELS` | `true` (default) uses deterministic mock model providers |
| `PROMPTER_ADMINS` | Comma-separated Nyquest user ids/emails allowed into the approval queue |

## API summary

Projects `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/{id}`.
Prompts `GET/POST /api/prompts`, `GET/PUT/DELETE /api/prompts/{id}`, `/clone`.
Versions `GET/POST /api/prompts/{id}/versions`, `/versions/{vid}/restore`, `/versions/{vid}/diff`.
Testing `POST /api/prompts/{id}/render|test|compare`, `GET .../test-runs`, providers.
Test cases `GET/POST /api/prompts/{id}/test-cases`, `DELETE /api/test-cases/{id}`.
Approvals `POST /api/prompts/{id}/submit-approval`, `GET /api/approvals`, `/approvals/{id}/approve|reject|request-changes`.
Templates `GET /api/templates`, `POST /api/templates/{id}/use`.
Export `GET /api/prompts/{id}/export/json|markdown`.

## Nyquest Prompt Package

`prompt.package.json` (schema_version `1.0`) — identity, prompt sections, variables,
model settings, output schema, governance, and test cases. Built by `backend/exporter.py`.

## Mock models

`backend/mockmodels.py` returns deterministic, provider-flavored responses with believable
metrics (latency / tokens / cost / quality / risk). Set `ENABLE_MOCK_MODELS=false` and wire a
real client keyed by provider/model to route through the real Nyquest multi-model router.

## Data model

`users`, `organizations`, `prompt_projects`, `prompts`, `prompt_versions`,
`prompt_test_cases`, `prompt_test_runs`, `prompt_approvals`, `audit_logs` — see `backend/database.py`.

## Deploy notes (prompter.zoidlab.ai)

Two systemd services behind the shared Cloudflare Tunnel: `prompter-web` (Next, :3400) and
`prompter-api` (FastAPI, :8400, localhost). The frontend proxies `/api/*` to the backend.
Add the hostname to the tunnel ingress and route DNS with `cloudflared tunnel route dns`.
