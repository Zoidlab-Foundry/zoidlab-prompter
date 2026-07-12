"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import type { Prompt } from "../../lib/types";
import { GovBadges, RiskBadge } from "../../components/Badges";

export default function Templates() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Prompt[]>([]);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => { api.templates().then(setTemplates).catch(() => {}); }, []);

  async function use(t: Prompt) {
    setBusy(t.id); setErr("");
    try { const r = await api.useTemplate(t.id); router.push(`/prompts/${r.prompt.id}/edit`); }
    catch (e: any) { setErr(e.status === 401 ? "Sign in with your Nyquest account to use a template." : e.message); setBusy(""); }
  }

  return (
    <div className="py-8">
      <h1 className="text-[22px] font-semibold">Prompt Templates</h1>
      <p className="mt-1 text-[13px] text-dim">Production-ready starting points. Use one to spin up a private, editable copy in your workspace.</p>
      {err && <div className="mt-3 rounded-lg border border-bad/40 bg-bad/10 px-4 py-2 text-[13px] text-bad">{err}</div>}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {templates.map((t) => (
          <div key={t.id} className="flex flex-col rounded-2xl border border-line bg-panel p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-[14px] font-semibold text-ink">{t.name.replace(" Prompt", "")}</h3>
              <RiskBadge risk={t.risk_level} />
            </div>
            <p className="mb-3 line-clamp-3 text-[12.5px] leading-relaxed text-dim">{t.system_prompt}</p>
            <div className="mb-3 flex flex-wrap gap-1.5">
              {(t.variables || []).slice(0, 4).map((v) => <span key={v.name} className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-ind">{`{{${v.name}}}`}</span>)}
            </div>
            <div className="mb-3"><GovBadges badges={t.badges} max={3} /></div>
            <button onClick={() => use(t)} disabled={!!busy} className="mt-auto rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">
              {busy === t.id ? "Creating…" : "Use template"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
