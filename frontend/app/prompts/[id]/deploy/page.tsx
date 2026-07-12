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
  { name: "Nyquest AI Concierge", desc: "Deploy to a customer AI concierge.", href: "#", live: false },
  { name: "Nyquest API", desc: "Serve this prompt via the Nyquest API.", href: "#", live: false },
];

export default function Deploy() {
  const { id } = useParams<{ id: string }>();
  const [p, setP] = useState<Prompt | null>(null);
  const [pkg, setPkg] = useState<any>(null);
  useEffect(() => {
    api.prompt(id).then(setP);
    fetch(api.exportJsonUrl(id), { credentials: "include" }).then((r) => r.json()).then(setPkg).catch(() => {});
  }, [id]);
  if (!p) return <div className="py-24 text-center text-faint">Loading…</div>;
  const approved = p.status === "approved" || p.status === "deployed" || p.governance?.approved_for_production;

  return (
    <div className="py-8">
      <Link href={`/prompts/${p.id}`} className="text-[12px] text-faint hover:text-dim">← {p.name}</Link>
      <h1 className="mt-3 text-[22px] font-semibold">Export & Deploy</h1>
      <p className="mt-1 text-[13px] text-dim">Package this prompt as a portable <b>Nyquest Prompt Package</b> and prepare it for a deployment target.</p>

      <div className={`mt-4 rounded-xl border px-4 py-3 text-[13px] ${approved ? "border-ok/40 bg-ok/10 text-ok" : "border-warn/40 bg-warn/10 text-warn"}`}>
        {approved ? "✓ Approved for production — ready to deploy." : "⚠ Not yet approved for production. Submit for approval before deploying to a live target."}
        <div className="mt-1"><GovBadges badges={p.badges} /></div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_360px]">
        <div>
          <h2 className="mb-3 text-[15px] font-semibold">Deployment targets</h2>
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
