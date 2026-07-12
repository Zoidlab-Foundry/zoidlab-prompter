"use client";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "../../../../lib/api";
import type { Prompt, RunResult, TestCase } from "../../../../lib/types";

const short = (m: string) => (m === "auto" ? "Nyquest Router" : (m.includes("/") ? m.split("/").pop()! : m).replace("-preview", ""));

export default function TestLab() {
  const { id } = useParams<{ id: string }>();
  const [p, setP] = useState<Prompt | null>(null);
  const [featured, setFeatured] = useState<string[]>([]);
  const [allModels, setAllModels] = useState<string[]>([]);
  const [live, setLive] = useState(false);
  const [billing, setBilling] = useState<string>("mock");
  const [sel, setSel] = useState<string[]>([]);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [cases, setCases] = useState<TestCase[]>([]);
  const [caseId, setCaseId] = useState("");
  const [results, setResults] = useState<RunResult[] | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.prompt(id).then((pr) => {
      setP(pr);
      const tv: Record<string, string> = {}; (pr.variables || []).forEach((v) => { tv[v.name] = v.example || ""; });
      setVals(tv);
    });
    api.models().then((m) => { setFeatured(m.featured); setAllModels(m.models); setLive(m.live); setBilling(m.billing || (m.live ? "owner" : "mock")); setSel(m.featured.slice(0, 4)); });
    api.testCases(id).then(setCases);
  }, [id]);

  const vars = useMemo(() => (p?.variables || []).map((v) => v.name), [p]);
  function pickCase(cid: string) {
    setCaseId(cid);
    const tc = cases.find((c) => c.id === cid);
    if (tc) setVals({ ...vals, ...Object.fromEntries(Object.entries(tc.input_variables).map(([k, v]) => [k, String(v)])) });
  }
  const toggle = (m: string) => setSel(sel.includes(m) ? sel.filter((x) => x !== m) : [...sel, m]);
  async function run() {
    setRunning(true); setResults(null);
    try { const r = await api.compare(id, { variables: vals, models: sel, test_case_id: caseId || undefined, save: true }); setResults(r.results); }
    finally { setRunning(false); }
  }

  if (!p) return <div className="py-24 text-center text-faint">Loading…</div>;

  return (
    <div className="py-8">
      <Link href={`/prompts/${p.id}`} className="text-[12px] text-faint hover:text-dim">← {p.name}</Link>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="text-[22px] font-semibold">Test Lab</h1>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] ${billing === "user" ? "border-ok/40 bg-ok/10 text-ok" : billing === "owner" ? "border-cy/40 bg-cy/10 text-cy" : "border-warn/40 bg-warn/10 text-warn"}`}>{billing === "user" ? "live Nyquest models · billed to your wallet" : billing === "owner" ? "live models · billed to the workspace key" : "mock models · no billing"}</span>
      </div>
      <p className="mt-1 text-[13px] text-dim">Run the prompt across the Nyquest models you pick and compare output, cost, latency, and quality side by side.</p>
      <p className="mt-2 inline-block rounded-md border border-warn/40 bg-warn/10 px-2.5 py-1 text-[11.5px] text-warn">Scoring note — <b>keyword match</b> and <b>JSON validity</b> are measured from your test case. <b>quality</b>, <b>safety</b> and <b>eval overall</b> are heuristic estimates, not a real evaluation model.</p>

      <div className="mt-5 grid gap-4 lg:grid-cols-[300px_1fr]">
        <div className="space-y-3">
          <div className="rounded-xl border border-line bg-panel p-4">
            <div className="mb-2 text-[11px] uppercase tracking-wider text-faint">Test case</div>
            <select value={caseId} onChange={(e) => pickCase(e.target.value)} className={inp}>
              <option value="">Custom input</option>
              {cases.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <div className="mt-3 space-y-2">
              {vars.map((v) => <label key={v} className="block"><span className="mb-1 block text-[11px] text-faint">{v}</span>
                <input value={vals[v] || ""} onChange={(e) => setVals({ ...vals, [v]: e.target.value })} className={inp} /></label>)}
              {!vars.length && <p className="text-[12px] text-faint">No variables.</p>}
            </div>
          </div>
          <div className="rounded-xl border border-line bg-panel p-4">
            <div className="mb-2 text-[11px] uppercase tracking-wider text-faint">Models ({sel.length})</div>
            <div className="flex flex-wrap gap-1.5">
              {Array.from(new Set([...featured, ...sel])).map((m) => (
                <button key={m} onClick={() => toggle(m)}
                  className={`rounded-full border px-2.5 py-1 text-[11px] ${sel.includes(m) ? "border-vi/60 bg-vi/15 text-ink" : "border-line text-dim"}`}>{short(m)}</button>
              ))}
            </div>
            <select value="" onChange={(e) => { if (e.target.value && !sel.includes(e.target.value)) setSel([...sel, e.target.value]); }} className={`${inp} mt-2`}>
              <option value="">+ Add another model…</option>
              {allModels.filter((m) => !sel.includes(m)).map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <button onClick={run} disabled={running || !sel.length} className="mt-3 w-full rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{running ? "Running…" : `Compare ${sel.length} model${sel.length === 1 ? "" : "s"}`}</button>
          </div>
        </div>

        <div>
          {!results ? (
            <div className="rounded-2xl border border-dashed border-line py-20 text-center text-[13px] text-faint">Pick models and run a comparison.</div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {results.map((r, i) => (
                <div key={r.provider + i} className={`flex flex-col rounded-2xl border p-4 ${(r as any).error ? "border-bad/40 bg-bad/5" : "border-line bg-panel"}`}>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="truncate text-[13px] font-semibold text-ink" title={r.model}>{r.label}</span>
                    <span className="rounded-full bg-ok/10 px-2 py-0.5 text-[10px] text-ok">eval {r.evaluation?.overall ?? "—"}</span>
                  </div>
                  <p className="mb-3 max-h-56 overflow-auto whitespace-pre-wrap text-[12px] leading-relaxed text-dim">{r.output}</p>
                  <div className="mt-auto grid grid-cols-3 gap-1.5 border-t border-line pt-3 text-center text-[10px]">
                    <Metric label="latency" value={`${r.latency_ms}ms`} />
                    <Metric label="cost" value={`$${(r.cost_estimate || 0).toFixed(4)}`} />
                    <Metric label="tokens" value={`${r.token_estimate}`} />
                    <Metric label="quality" value={r.metrics?.quality_score != null ? `${r.metrics.quality_score}` : "—"} />
                    <Metric label="kw match" value={`${r.evaluation?.keyword_match ?? "—"}`} />
                    <Metric label="safety" value={`${r.evaluation?.safety ?? "—"}`} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><div className="font-medium text-ink">{value}</div><div className="text-faint">{label}</div></div>;
}
const inp = "w-full rounded-lg border border-line bg-panel2 px-2.5 py-2 text-[12.5px] text-ink outline-none focus:border-vi/60";
