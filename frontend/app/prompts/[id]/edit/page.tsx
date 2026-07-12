"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "../../../../lib/api";
import type { Prompt, Variable, RunResult } from "../../../../lib/types";
import { StatusBadge, RiskBadge } from "../../../../components/Badges";
import { CATEGORIES } from "../../../../lib/ui";

const SECTIONS: [keyof Prompt, string, string][] = [
  ["system_prompt", "System", "You are an AI assistant for {{business_name}}…"],
  ["developer_prompt", "Developer", "Use only the provided context. Guardrails…"],
  ["user_prompt", "User", "{{user_message}}"],
  ["tool_prompt", "Tools", "Tool / function instructions…"],
];

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [p, setP] = useState<Prompt | null>(null);
  const [dirty, setDirty] = useState(false);
  const [sec, setSec] = useState<keyof Prompt>("system_prompt");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [testVals, setTestVals] = useState<Record<string, string>>({});
  const [result, setResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [showVersion, setShowVersion] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [live, setLive] = useState(false);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { api.models().then((m) => { setModels(m.models); setLive(m.live); }).catch(() => {}); }, []);
  useEffect(() => {
    api.prompt(id).then((pr) => {
      setP(pr);
      const tv: Record<string, string> = {};
      (pr.variables || []).forEach((v) => { tv[v.name] = v.example || ""; });
      setTestVals(tv);
    }).catch(() => setMsg("Could not load (private or not found)."));
  }, [id]);

  const vars = useMemo(() => {
    if (!p) return [] as string[];
    const t = `${p.system_prompt || ""} ${p.developer_prompt || ""} ${p.user_prompt || ""} ${p.tool_prompt || ""}`;
    return Array.from(new Set([...(t.match(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g) || []).map((m) => m.replace(/[{}\s]/g, ""))]));
  }, [p]);

  if (!p) return <div className="py-24 text-center text-faint">{msg || "Loading editor…"}</div>;
  const set = (patch: Partial<Prompt>) => { setP({ ...p, ...patch }); setDirty(true); };
  const setMs = (patch: any) => set({ model_settings: { ...p.model_settings, ...patch } });
  const setGov = (patch: any) => set({ governance: { ...p.governance, ...patch }, ...(patch.risk_level ? { risk_level: patch.risk_level } : {}) });

  function insertVar(name: string) {
    const ta = taRef.current; if (!ta) return;
    const cur = (p as any)[sec] || "";
    const at = ta.selectionStart ?? cur.length;
    set({ [sec]: cur.slice(0, at) + `{{${name}}}` + cur.slice(at) } as any);
  }

  async function saveDraft() {
    setSaving(true); setMsg("");
    try {
      await api.updatePrompt(p!.id, {
        name: p!.name, description: p!.description, category: p!.category, status: p!.status, risk_level: p!.risk_level,
        system_prompt: p!.system_prompt, developer_prompt: p!.developer_prompt, user_prompt: p!.user_prompt, tool_prompt: p!.tool_prompt,
        variables: p!.variables, model_settings: p!.model_settings, governance: p!.governance, output_schema: p!.output_schema,
      });
      setDirty(false); setMsg("Saved.");
    } catch (e: any) { setMsg(e.status === 401 ? "Sign in with your Nyquest account to save." : e.message); } finally { setSaving(false); }
  }

  async function runTest() {
    setRunning(true); setResult(null);
    try { setResult(await api.test(p!.id, { variables: testVals, model: p!.model_settings.model, save: true })); }
    catch (e: any) { setMsg(e.message); } finally { setRunning(false); }
  }

  return (
    <div className="py-6">
      {/* top bar */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Link href={`/prompts/${p.id}`} className="text-[12px] text-faint hover:text-dim">← {p.name}</Link>
        <span className="rounded-md border border-line px-2 py-0.5 text-[11px] text-dim">v{p.current_version}</span>
        <StatusBadge status={p.status} /><RiskBadge risk={p.risk_level} />
        {dirty && <span className="text-[11px] text-warn">● unsaved changes</span>}
        <div className="ml-auto flex items-center gap-2">
          {msg && <span className="text-[11px] text-dim">{msg}</span>}
          <button onClick={saveDraft} disabled={saving} className="rounded-lg border border-line px-4 py-2 text-[13px] text-ink hover:bg-white/5 disabled:opacity-50">{saving ? "Saving…" : "Save Draft"}</button>
          <button onClick={() => setShowVersion(true)} className="rounded-lg border border-line px-4 py-2 text-[13px] text-ink hover:bg-white/5">Save Version</button>
          <Link href={`/prompts/${p.id}/deploy`} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">Export</Link>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr_320px]">
        {/* LEFT: metadata + variables + model + governance */}
        <div className="space-y-3">
          <Panel title="Metadata">
            <Field label="Name"><input value={p.name} onChange={(e) => set({ name: e.target.value })} className={inp} /></Field>
            <Field label="Category"><select value={p.category} onChange={(e) => set({ category: e.target.value })} className={inp}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></Field>
            <Field label="Status"><select value={p.status} onChange={(e) => set({ status: e.target.value })} className={inp}>{["draft", "testing", "pending_approval", "approved", "deployed", "deprecated"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></Field>
            <Field label="Description"><textarea value={p.description} onChange={(e) => set({ description: e.target.value })} rows={2} className={inp} /></Field>
          </Panel>
          <Panel title={`Variables (${(p.variables || []).length})`}>
            {(p.variables || []).map((v, i) => (
              <div key={i} className="mb-2 rounded-lg border border-line bg-panel2 p-2">
                <div className="flex items-center gap-1.5">
                  <input value={v.name} onChange={(e) => { const nv = [...p.variables]; nv[i] = { ...v, name: e.target.value }; set({ variables: nv }); }} className="w-full rounded bg-transparent font-mono text-[11px] text-ind outline-none" />
                  <button onClick={() => { const nv = p.variables.filter((_, j) => j !== i); set({ variables: nv }); }} className="text-faint hover:text-bad">✕</button>
                </div>
                <div className="mt-1 flex gap-1.5">
                  <select value={v.type} onChange={(e) => { const nv = [...p.variables]; nv[i] = { ...v, type: e.target.value }; set({ variables: nv }); }} className="rounded bg-panel px-1 py-0.5 text-[10px] text-dim">{["string", "text", "number", "boolean", "date", "JSON", "URL", "file"].map((t) => <option key={t}>{t}</option>)}</select>
                  <input placeholder="example" value={v.example || ""} onChange={(e) => { const nv = [...p.variables]; nv[i] = { ...v, example: e.target.value }; set({ variables: nv }); }} className="w-full rounded bg-panel px-1 py-0.5 text-[10px] text-dim outline-none" />
                </div>
              </div>
            ))}
            <button onClick={() => set({ variables: [...(p.variables || []), { name: "new_var", type: "string", required: false } as Variable] })} className="w-full rounded-lg border border-dashed border-line py-1.5 text-[11px] text-dim hover:text-ink">+ Add variable</button>
            {vars.filter((v) => !(p.variables || []).some((pv) => pv.name === v)).length > 0 && (
              <div className="mt-2 text-[10px] text-warn">Used but undefined: {vars.filter((v) => !(p.variables || []).some((pv) => pv.name === v)).join(", ")}</div>
            )}
          </Panel>
          <Panel title="Model settings">
            <Field label="Model">
              <select value={p.model_settings.model} onChange={(e) => setMs({ model: e.target.value, provider: e.target.value === "auto" ? "nyquest-router" : (e.target.value.split("/")[0] || "nyquest-router") })} className={inp}>
                {!models.includes(p.model_settings.model) && <option value={p.model_settings.model}>{p.model_settings.model}</option>}
                {models.map((m) => <option key={m} value={m}>{m === "auto" ? "auto (Nyquest Router)" : m}</option>)}
              </select>
            </Field>
            <Field label="Fallback model"><select value={p.model_settings.fallback_model || ""} onChange={(e) => setMs({ fallback_model: e.target.value })} className={inp}><option value="">none</option>{models.map((m) => <option key={m} value={m}>{m}</option>)}</select></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label={`Temp ${p.model_settings.temperature}`}><input type="range" min={0} max={2} step={0.1} value={p.model_settings.temperature} onChange={(e) => setMs({ temperature: +e.target.value })} className="w-full" /></Field>
              <Field label="Max tokens"><input type="number" value={p.model_settings.max_tokens} onChange={(e) => setMs({ max_tokens: +e.target.value })} className={inp} /></Field>
            </div>
            <label className="mt-1 flex items-center gap-2 text-[12px] text-dim"><input type="checkbox" checked={!!p.model_settings.json_mode} onChange={(e) => setMs({ json_mode: e.target.checked })} /> JSON mode</label>
          </Panel>
          <Panel title="Governance">
            <Field label="Risk level"><select value={p.governance.risk_level} onChange={(e) => setGov({ risk_level: e.target.value })} className={inp}>{["low", "medium", "high"].map((r) => <option key={r}>{r}</option>)}</select></Field>
            <Field label="PII risk"><select value={p.governance.pii_risk} onChange={(e) => setGov({ pii_risk: e.target.value })} className={inp}>{["low", "medium", "high"].map((r) => <option key={r}>{r}</option>)}</select></Field>
            <label className="flex items-center gap-2 text-[12px] text-dim"><input type="checkbox" checked={!!p.governance.requires_human_approval} onChange={(e) => setGov({ requires_human_approval: e.target.checked })} /> Human approval required</label>
          </Panel>
        </div>

        {/* CENTER: prompt sections */}
        <div>
          <div className="mb-2 flex items-center gap-1 border-b border-line">
            {SECTIONS.map(([k, label]) => <button key={k} onClick={() => setSec(k)} className={`px-3 py-2 text-[12px] ${sec === k ? "border-b-2 border-vi text-ink" : "text-dim hover:text-ink"}`}>{label}{(p as any)[k] ? "" : " ·"}</button>)}
          </div>
          {vars.length > 0 && (
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] text-faint">Insert:</span>
              {vars.map((v) => <button key={v} onClick={() => insertVar(v)} className="rounded bg-ind/15 px-1.5 py-0.5 font-mono text-[10px] text-ind hover:bg-ind/25">{`{{${v}}}`}</button>)}
            </div>
          )}
          <textarea ref={taRef} value={(p as any)[sec] || ""} onChange={(e) => set({ [sec]: e.target.value } as any)}
            rows={20} placeholder={SECTIONS.find(([k]) => k === sec)?.[2]}
            className="w-full resize-y rounded-xl border border-line bg-panel2 p-4 font-mono text-[13px] leading-relaxed text-ink outline-none focus:border-vi/60" />
          <div className="mt-3">
            <div className="mb-1 text-[11px] uppercase tracking-wider text-faint">Output schema (JSON)</div>
            <textarea value={JSON.stringify(p.output_schema || {}, null, 2)} onChange={(e) => { try { set({ output_schema: JSON.parse(e.target.value) }); } catch { /* keep typing */ } }}
              rows={5} className="w-full resize-y rounded-xl border border-line bg-panel2 p-3 font-mono text-[11px] text-dim outline-none focus:border-vi/60" />
          </div>
        </div>

        {/* RIGHT: test runner + preview */}
        <div className="space-y-3">
          <Panel title="Test inputs">
            {vars.length === 0 && <p className="text-[12px] text-faint">No variables to fill.</p>}
            {vars.map((v) => <Field key={v} label={v}><input value={testVals[v] || ""} onChange={(e) => setTestVals({ ...testVals, [v]: e.target.value })} className={inp} /></Field>)}
            <button onClick={runTest} disabled={running} className="mt-2 w-full rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{running ? "Running…" : `Run · ${p.model_settings.model === "auto" ? "Nyquest Router" : p.model_settings.model.split("/").pop()}`}</button>
            <div className="mt-1.5 text-center text-[10px] text-faint">{live ? "live · billed to your Nyquest wallet" : "mock model"}</div>
            <Link href={`/prompts/${p.id}/test`} className="mt-2 block text-center text-[11px] text-cy hover:underline">Compare across models →</Link>
          </Panel>
          {result && (
            <Panel title={`Output · ${result.label}`}>
              <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink">{result.output}</p>
              <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-faint">
                <span className="rounded bg-white/5 px-1.5 py-0.5">{result.latency_ms}ms</span>
                <span className="rounded bg-white/5 px-1.5 py-0.5">${result.cost_estimate.toFixed(4)}</span>
                <span className="rounded bg-white/5 px-1.5 py-0.5">{result.token_estimate} tok</span>
                <span className="rounded bg-ok/10 px-1.5 py-0.5 text-ok">eval {result.evaluation.overall}</span>
              </div>
            </Panel>
          )}
        </div>
      </div>

      {showVersion && <SaveVersion current={p.current_version} onClose={() => setShowVersion(false)} onSave={async (version, changelog) => {
        await saveDraft(); await api.saveVersion(p.id, version, changelog); setShowVersion(false); router.refresh(); setMsg(`Saved v${version}`); setP({ ...p, current_version: version });
      }} />}
    </div>
  );
}

function SaveVersion({ current, onClose, onSave }: { current: string; onClose: () => void; onSave: (v: string, c: string) => Promise<void> }) {
  const bump = (kind: "minor" | "major") => {
    const [a, b, c] = current.split(".").map((n) => parseInt(n) || 0);
    return kind === "major" ? `${a + 1}.0.0` : `${a}.${b + 1}.0`;
  };
  const [version, setVersion] = useState(bump("minor"));
  const [changelog, setChangelog] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl border border-line bg-panel2 p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-3 text-[16px] font-semibold">Save version</h2>
        <div className="mb-3 flex gap-2">
          <button onClick={() => setVersion(bump("minor"))} className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-dim hover:text-ink">Minor {bump("minor")}</button>
          <button onClick={() => setVersion(bump("major"))} className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-dim hover:text-ink">Major {bump("major")}</button>
        </div>
        <label className="mb-3 block"><span className="mb-1 block text-[12px] text-faint">Version</span><input value={version} onChange={(e) => setVersion(e.target.value)} className={inp} /></label>
        <label className="mb-4 block"><span className="mb-1 block text-[12px] text-faint">Changelog</span><textarea value={changelog} onChange={(e) => setChangelog(e.target.value)} rows={3} placeholder="What changed?" className={inp} /></label>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-line px-4 py-2 text-[13px] text-dim hover:text-ink">Cancel</button>
          <button onClick={async () => { setBusy(true); try { await onSave(version, changelog); } finally { setBusy(false); } }} disabled={busy} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{busy ? "Saving…" : "Save version"}</button>
        </div>
      </div>
    </div>
  );
}

const inp = "w-full rounded-lg border border-line bg-panel px-2.5 py-2 text-[12.5px] text-ink outline-none focus:border-vi/60";
function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="rounded-xl border border-line bg-panel p-3"><div className="mb-2 text-[11px] uppercase tracking-wider text-faint">{title}</div>{children}</div>;
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="mb-2 block"><span className="mb-1 block text-[11px] text-faint">{label}</span>{children}</label>;
}
