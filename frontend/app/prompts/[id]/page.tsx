"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "../../../lib/api";
import type { Prompt } from "../../../lib/types";
import { GovBadges, StatusBadge, RiskBadge } from "../../../components/Badges";

const TABS = ["Overview", "Prompt", "Variables", "Test Cases", "Evaluations", "Versions", "Deployment", "Audit Log"];

export default function PromptDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [p, setP] = useState<Prompt | null>(null);
  const [tab, setTab] = useState("Overview");
  const [audit, setAudit] = useState<any[]>([]);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<{ k: "ok" | "err"; t: string } | null>(null);

  const load = () => api.prompt(id).then(setP).catch(() => setP(null));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);
  useEffect(() => { if (tab === "Audit Log") api.audit(id).then(setAudit).catch(() => {}); }, [tab, id]);

  if (p === null) return <div className="py-24 text-center text-faint">Loading prompt…</div>;
  const gov = p.governance || {};
  const ms = p.model_settings || {};
  const runs = p.latest_runs || [];

  async function act(kind: "clone" | "submit") {
    setBusy(kind); setMsg(null);
    try {
      if (kind === "clone") { const r = await api.clonePrompt(p!.id); router.push(`/prompts/${r.prompt.id}/edit`); }
      else { await api.submitApproval(p!.id); setMsg({ k: "ok", t: "Submitted for approval." }); load(); }
    } catch (e: any) { setMsg({ k: "err", t: e.status === 401 ? "Sign in required." : e.message }); } finally { setBusy(""); }
  }

  return (
    <div className="py-8">
      <Link href="/prompts" className="text-[12px] text-faint hover:text-dim">← Library</Link>
      <div className="mt-4 flex flex-col gap-4 rounded-2xl border border-line bg-panel p-6 sm:flex-row sm:items-start">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[24px] font-bold">{p.name}</h1>
            <StatusBadge status={p.status} /><RiskBadge risk={p.risk_level} />
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-dim">
            <span>v{p.current_version}</span><span className="text-line">·</span>
            <span className="rounded bg-white/5 px-1.5 py-0.5">{p.category}</span>
            {p.project && <><span className="text-line">·</span><Link href={`/projects/${p.project.id}`} className="text-cy hover:underline">{p.project.name}</Link></>}
          </div>
          <p className="mt-3 max-w-2xl text-[13.5px] leading-relaxed text-dim">{p.description}</p>
          <div className="mt-3"><GovBadges badges={p.badges} /></div>
        </div>
        <div className="flex shrink-0 flex-col gap-2">
          <Link href={`/prompts/${p.id}/edit`} className="rounded-lg bg-vi px-5 py-2.5 text-center text-[13px] font-semibold text-white hover:opacity-90">Edit</Link>
          <Link href={`/prompts/${p.id}/test`} className="rounded-lg border border-line px-5 py-2.5 text-center text-[13px] text-ink hover:bg-white/5">Test Lab</Link>
          <div className="flex gap-2">
            <button onClick={() => act("clone")} disabled={!!busy} className="flex-1 rounded-lg border border-line px-3 py-2 text-[12px] text-dim hover:text-ink disabled:opacity-50">Clone</button>
            <Link href={`/prompts/${p.id}/deploy`} className="flex-1 rounded-lg border border-line px-3 py-2 text-center text-[12px] text-dim hover:text-ink">Export</Link>
          </div>
          {p.status !== "approved" && p.status !== "pending_approval" && (
            <button onClick={() => act("submit")} disabled={!!busy} className="rounded-lg border border-vi/50 px-5 py-2 text-[12px] text-vi hover:bg-vi/10 disabled:opacity-50">Submit for approval</button>
          )}
        </div>
      </div>
      {msg && <div className={`mt-3 rounded-lg border px-4 py-2 text-[13px] ${msg.k === "ok" ? "border-ok/40 bg-ok/10 text-ok" : "border-bad/40 bg-bad/10 text-bad"}`}>{msg.t}</div>}

      <div className="mt-6 flex flex-wrap gap-1 border-b border-line">
        {TABS.map((t) => <button key={t} onClick={() => setTab(t)} className={`px-3 py-2 text-[13px] ${tab === t ? "border-b-2 border-vi text-ink" : "text-dim hover:text-ink"}`}>{t}</button>)}
      </div>

      <div className="py-5">
        {tab === "Overview" && (
          <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
            <div className="space-y-3">
              <Card title="Description"><p className="text-[13px] leading-relaxed text-dim">{p.description || "No description."}</p></Card>
              <Card title="Model target"><p className="text-[13px] text-dim">{ms.provider} · {ms.model} · temp {ms.temperature} · {ms.max_tokens} tok {ms.json_mode ? "· JSON mode" : ""}</p></Card>
              {runs.length > 0 && <Card title="Latest test runs">
                {runs.slice(0, 5).map((r: any) => <div key={r.id} className="flex items-center justify-between border-b border-line py-1.5 text-[12px] last:border-0">
                  <span className="text-dim">{r.provider}</span><span className="text-faint">{r.latency_ms}ms · ${Number(r.cost_estimate).toFixed(4)} · eval {(r.evaluation?.overall ?? 0)}</span></div>)}
              </Card>}
            </div>
            <div className="space-y-3">
              <Card title="Governance">
                <dl className="space-y-1.5 text-[12px]">
                  <Row k="Risk level" v={gov.risk_level} /><Row k="PII risk" v={gov.pii_risk} />
                  <Row k="Human approval" v={gov.requires_human_approval ? "required" : "no"} />
                  <Row k="Logs prompts" v={gov.logs_prompts ? "yes" : "no"} /><Row k="Logs outputs" v={gov.logs_outputs ? "yes" : "no"} />
                  <Row k="Prod approved" v={gov.approved_for_production ? "yes" : "no"} />
                </dl>
              </Card>
            </div>
          </div>
        )}
        {tab === "Prompt" && (
          <div className="space-y-4">
            {([["system_prompt", "System"], ["developer_prompt", "Developer"], ["user_prompt", "User"], ["tool_prompt", "Tool / functions"]] as const).map(([k, label]) =>
              (p as any)[k] ? <div key={k}><div className="mb-1 text-[11px] uppercase tracking-wider text-faint">{label}</div>
                <pre className="overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-panel2 p-3 text-[12.5px] text-ink">{highlight((p as any)[k])}</pre></div> : null)}
          </div>
        )}
        {tab === "Variables" && <VarTable variables={p.variables} />}
        {tab === "Test Cases" && (
          <div className="space-y-2">
            {(p.test_cases || []).map((t) => <div key={t.id} className="rounded-xl border border-line bg-panel2 p-3">
              <div className="text-[13px] font-medium text-ink">{t.name}</div>
              <div className="mt-1 font-mono text-[11px] text-dim">{JSON.stringify(t.input_variables)}</div>
              <div className="mt-1 text-[11px] text-faint">expect: {t.expected_keywords.join(", ") || "—"} · avoid: {t.negative_keywords.join(", ") || "—"}</div>
            </div>)}
            {!(p.test_cases || []).length && <p className="text-[13px] text-faint">No test cases. Add them in the Test Lab.</p>}
          </div>
        )}
        {tab === "Evaluations" && (runs.length ? (
          <div className="space-y-2">
            {runs.map((r: any) => <div key={r.id} className="rounded-xl border border-line bg-panel2 p-3">
              <div className="mb-1 flex justify-between text-[12px]"><span className="text-ink">{r.provider}</span><span className="text-faint">overall {r.evaluation?.overall ?? "—"}</span></div>
              <div className="flex flex-wrap gap-2 text-[11px] text-dim">{Object.entries(r.evaluation || {}).filter(([k]) => !["negative_keyword_hit"].includes(k)).map(([k, v]) => <span key={k} className="rounded bg-white/5 px-1.5 py-0.5">{k}: {String(v)}</span>)}</div>
            </div>)}
          </div>) : <p className="text-[13px] text-faint">Run a test to see evaluations.</p>)}
        {tab === "Versions" && (
          <div className="space-y-2">
            {(p.versions || []).map((v) => <div key={v.id} className="flex items-center justify-between rounded-xl border border-line bg-panel2 p-3 text-[13px]">
              <span className="font-medium text-ink">v{v.version}</span><span className="text-dim">{v.changelog}</span><span className="text-faint">{v.created_at?.slice(0, 10)}</span></div>)}
            <Link href={`/prompts/${p.id}/versions`} className="mt-2 inline-block text-[12px] text-cy hover:underline">Full version history + diff →</Link>
          </div>
        )}
        {tab === "Deployment" && <Link href={`/prompts/${p.id}/deploy`} className="inline-block rounded-lg bg-vi px-5 py-2.5 text-[13px] font-semibold text-white hover:opacity-90">Open deployment & export →</Link>}
        {tab === "Audit Log" && (
          <div className="space-y-1.5">
            {audit.map((a) => <div key={a.id} className="flex items-center justify-between rounded-lg border border-line bg-panel2 px-3 py-2 text-[12px]">
              <span className="text-dim">{a.action}</span><span className="text-faint">{a.actor_user_id ? a.actor_user_id.slice(0, 8) : "system"} · {a.created_at?.slice(0, 16).replace("T", " ")}</span></div>)}
            {!audit.length && <p className="text-[13px] text-faint">No audit entries.</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="rounded-xl border border-line bg-panel p-4"><div className="mb-2 text-[11px] uppercase tracking-wider text-faint">{title}</div>{children}</div>;
}
function Row({ k, v }: { k: string; v: any }) { return <div className="flex justify-between"><dt className="text-faint">{k}</dt><dd className="text-dim">{String(v)}</dd></div>; }
function VarTable({ variables }: { variables: any[] }) {
  if (!variables?.length) return <p className="text-[13px] text-faint">No variables defined.</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-left text-[12.5px]">
        <thead className="bg-panel2 text-faint"><tr>{["Variable", "Type", "Required", "Description", "Example"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
        <tbody>{variables.map((v) => <tr key={v.name} className="border-t border-line">
          <td className="px-3 py-2 font-mono text-ind">{`{{${v.name}}}`}</td><td className="px-3 py-2 text-dim">{v.type}</td>
          <td className="px-3 py-2 text-dim">{v.required ? "yes" : "no"}</td><td className="px-3 py-2 text-dim">{v.description}</td>
          <td className="px-3 py-2 text-faint">{v.example}</td></tr>)}</tbody>
      </table>
    </div>
  );
}
function highlight(text: string) {
  const parts = text.split(/(\{\{[^}]+\}\})/g);
  return parts.map((s, i) => /^\{\{/.test(s) ? <span key={i} className="rounded bg-ind/15 px-0.5 text-ind">{s}</span> : <span key={i}>{s}</span>);
}
