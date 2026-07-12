import Link from "next/link";
import type { Prompt } from "../lib/types";
import { StatusBadge, RiskBadge } from "./Badges";

export default function PromptCard({ prompt }: { prompt: Prompt }) {
  return (
    <Link href={`/prompts/${prompt.id}`}
      className="group flex flex-col rounded-2xl border border-line bg-panel p-4 transition hover:border-vi/50 hover:shadow-glow">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-[14px] font-semibold text-ink">{prompt.name}</h3>
          <div className="mt-0.5 flex items-center gap-2 text-[11px] text-faint">
            <span className="rounded bg-white/5 px-1.5 py-0.5 text-dim">{prompt.category}</span>
            <span>v{prompt.current_version}</span>
          </div>
        </div>
        <span className="rounded-md border border-line px-1.5 py-0.5 font-mono text-[10px] text-faint">{prompt.slug?.split("-").slice(0, -1).join("-").slice(0, 14) || "prompt"}</span>
      </div>
      <p className="mb-3 line-clamp-2 text-[12.5px] leading-relaxed text-dim">{prompt.description}</p>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {(prompt.tags || []).slice(0, 3).map((t) => <span key={t} className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] text-faint">{t}</span>)}
      </div>
      <div className="mt-auto flex items-center justify-between border-t border-line pt-3">
        <StatusBadge status={prompt.status} />
        <RiskBadge risk={prompt.risk_level} />
      </div>
    </Link>
  );
}
