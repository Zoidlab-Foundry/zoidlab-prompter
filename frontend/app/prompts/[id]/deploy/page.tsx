"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "../../../../lib/api";
import type { Prompt } from "../../../../lib/types";
import { GovBadges } from "../../../../components/Badges";

const TARGETS = [
  { name: "ZoidLab Workflow Builder", desc: "Use this prompt inside a workflow node.", href: "https://builder.zoidlab.ai", live: true },
  { name: "ZoidLab Marketplace Agent", desc: "Attach this prompt to a marketplace agent.", href: "https://marketplace.zoidlab.ai", live: true },
];

export default function Deploy() {
  const { id } = useParams<{ id: string }>();
  const [p, setP] = useState<Prompt | null>(null);
  const [pkg, setPkg] = useState<any>(null);
  const [dep, setDep] = useState<any>(null); const [busy, setBusy] = useState(false); const [copied, setCopied] = useState(false);
  const loadDep = () => api.promptDeployment(id).then(setDep).catch(() => {});
  useEffect(() => {
    api.prompt(id).then(setP); loadDep();
    fetch(api.exportJsonUrl(id), { credentials: "include" }).then((r) => r.json()).then(setPkg).catch(() => {});
  }, [id]);
  const origin = typeof window !== "undefined" ? window.location.origin : "https://prompter.zoidlab.ai";
  const endpoint = dep?.enabled ? `${origin}/api/prompt-endpoint/${dep.token}/run` : null;
  const vars = (p?.variables || []).map((v: any) => v.name);
  const exampleVars = Object.fromEntries(vars.map((v: string) => [v, "..."]));
  const curl = endpoint ? `curl -s ${endpoint} \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify({ variables: exampleVars })}'` : "";
  async function deploy() { setBusy(true); try { await api.deployPrompt(id, {}); await loadDep(); } finally { setBusy(false); } }
  async function undeploy() { setBusy(true); try { await api.undeployPrompt(id); await loadDep(); } finally { setBusy(false); } }
  if (!p) return <div className="py-24 text-center text-faint">Loading…</div>;
  const approved = p.status === "approved" || p.status === "deployed" || p.governance?.approved_for_production;

  return (
    <div className="py-8">
      <Link href={`/prompts/${p.id}`} className="text-[12px] text-faint hover:text-dim">← {p.name}</Link>
      <h1 className="mt-3 text-[22px] font-semibold">Export & Deploy</h1>
      <p className="mt-1 text-[13px] text-dim">Serve this prompt as a live HTTP API, or package it as a portable <b>Nyquest Prompt Package</b>.</p>

      <div className={`mt-4 rounded-xl border px-4 py-3 text-[13px] ${approved ? "border-ok/40 bg-ok/10 text-ok" : "border-warn/40 bg-warn/10 text-warn"}`}>
        {approved ? "✓ Approved for production — ready to deploy." : "⚠ Not yet approved for production. You can still deploy for testing; approve before production use."}
        <div className="mt-1"><GovBadges badges={p.badges} /></div>
      </div>

      <div className="mt-6 rounded-2xl border border-vi/40 bg-vi/5 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-[15px] font-semibold text-ink">Live prompt API</h2>
            <p className="mt-0.5 text-[12.5px] text-dim">A token-authed endpoint: POST variables, get the model's output. Runs bill your Nyquest wallet.</p>
          </div>
          {endpoint
            ? <button onClick={undeploy} disabled={busy} className="rounded-lg border border-bad/40 px-4 py-2 text-[13px] text-bad hover:bg-bad/10 disabled:opacity-50">{busy ? "…" : "Disable endpoint"}</button>
            : <button onClick={deploy} disabled={busy} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{busy ? "Deploying…" : "Deploy as API"}</button>}
        </div>
        {endpoint && (
          <div className="mt-4 space-y-2">
            <div className="flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded-lg border border-line bg-panel2 px-3 py-2 text-[12px] text-cy">{endpoint}</code>
              <button onClick={() => { navigator.clipboard?.writeText(endpoint); setCopied(true); setTimeout(() => setCopied(false), 1200); }} className="rounded-lg border border-line px-3 py-2 text-[12px] text-dim hover:text-ink">{copied ? "Copied" : "Copy"}</button>
            </div>
            <pre className="overflow-x-auto rounded-lg border border-line bg-panel2 p-3 text-[11.5px] leading-relaxed text-dim">{curl}</pre>
            <div className="text-[11px] text-faint">{dep.call_count ?? 0} call{(dep.call_count ?? 0) === 1 ? "" : "s"} · snapshot of the prompt at deploy time · the token is the credential — keep it secret.</div>
          </div>
        )}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_360px]">
        <div>
          <h2 className="mb-3 text-[15px] font-semibold">Use in another Foundry app</h2>
          <div className="space-y-2">
            {TARGETS.map((t) => (
              <div key={t.name} className="flex items-center justify-between rounded-xl border border-line bg-panel p-3">
                <div><div className="text-[13px] font-medium text-ink">{t.name}</div><div className="text-[12px] text-dim">{t.desc}</div></div>
                {t.live
                  ? <a href={t.href} target="_blank" rel="noopener" className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-cy hover:bg-white/5">Open</a>
                  : <span className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-faint">Soon</span>}
              </div>
            ))}
          </div>

          <h2 className="mb-3 mt-6 text-[15px] font-semibold">Export</h2>
          <div className="flex flex-wrap gap-2">
            <a href={api.exportJsonUrl(p.id)} target="_blank" rel="noopener" className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">Download JSON package</a>
            <a href={api.exportMdUrl(p.id)} target="_blank" rel="noopener" className="rounded-lg border border-line px-4 py-2 text-[13px] text-ink hover:bg-white/5">Download Markdown</a>
            <span className="rounded-lg border border-line px-4 py-2 text-[13px] text-faint">YAML · soon</span>
          </div>
        </div>

        <div>
          <div className="mb-2 text-[11px] uppercase tracking-wider text-faint">prompt.package.json</div>
          <pre className="max-h-[520px] overflow-auto rounded-xl border border-line bg-panel2 p-3 text-[11px] leading-relaxed text-dim">{pkg ? JSON.stringify(pkg, null, 2) : "…"}</pre>
        </div>
      </div>
    </div>
  );
}
