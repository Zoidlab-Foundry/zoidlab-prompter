"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";
import type { Prompt, Project, Stats } from "../lib/types";
import PromptCard from "../components/PromptCard";

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-panel p-4">
      <div className="text-[22px] font-bold text-ink">{value}</div>
      <div className="text-[11px] uppercase tracking-wider text-faint">{label}</div>
      {sub && <div className="mt-0.5 text-[11px] text-dim">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
    api.prompts({ sort: "updated" }).then((d) => setPrompts(d.prompts)).catch(() => {});
    api.projects().then(setProjects).catch(() => {});
  }, []);

  const approved = prompts.filter((p) => p.status === "approved" || p.status === "deployed").slice(0, 3);
  const drafts = prompts.filter((p) => p.status === "draft").slice(0, 3);

  return (
    <div className="relative py-10">
      <div className="hero-glow" />
      <section className="relative z-10 mb-8">
        <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-panel px-3 py-1 text-[11px] text-dim">
          <span className="h-1.5 w-1.5 rounded-full bg-vi" /> Prompt lifecycle management for Nyquest
        </span>
        <h1 className="text-[34px] font-bold leading-tight sm:text-[40px]">ZoidLab <span className="prism-text">Prompter</span></h1>
        <p className="mt-2 max-w-xl text-[15px] text-dim">Design, test, version, and deploy production-ready AI prompts.</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link href="/prompts?new=1" className="rounded-xl bg-vi px-5 py-2.5 text-[13px] font-semibold text-white hover:opacity-90">Create Prompt</Link>
          <Link href="/projects?new=1" className="rounded-xl border border-line px-5 py-2.5 text-[13px] text-ink hover:bg-white/5">Create Project</Link>
          <Link href="/prompts" className="rounded-xl border border-line px-5 py-2.5 text-[13px] text-ink hover:bg-white/5">View Library</Link>
        </div>
      </section>

      {stats && (
        <section className="relative z-10 mb-10 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Total Prompts" value={stats.total} />
          <Stat label="Approved" value={stats.approved} />
          <Stat label="Drafts" value={stats.draft} />
          <Stat label="Test Runs" value={stats.test_runs} />
          <Stat label="Avg Cost" value={`$${stats.avg_cost.toFixed(4)}`} />
          <Stat label="Avg Latency" value={`${stats.avg_latency}ms`} />
        </section>
      )}

      <Section title="Recently edited" href="/prompts" items={prompts.slice(0, 6)} />
      {approved.length > 0 && <Section title="Approved prompts" href="/prompts?status=approved" items={approved} />}
      {drafts.length > 0 && <Section title="Draft prompts" href="/prompts?status=draft" items={drafts} />}

      <section className="relative z-10 mt-10">
        <div className="mb-4 flex items-end justify-between">
          <h2 className="text-[18px] font-semibold">Projects</h2>
          <Link href="/projects" className="text-[12px] text-cy hover:underline">All projects →</Link>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {projects.slice(0, 8).map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="flex items-center gap-3 rounded-xl border border-line bg-panel p-3 hover:border-vi/50">
              <span className="grid h-9 w-9 place-items-center rounded-lg text-[18px]" style={{ background: `${p.accent}22` }}>{p.icon}</span>
              <div className="min-w-0"><div className="truncate text-[13px] font-medium text-ink">{p.name}</div><div className="text-[11px] text-faint">{p.prompt_count} prompts</div></div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function Section({ title, href, items }: { title: string; href: string; items: Prompt[] }) {
  if (!items.length) return null;
  return (
    <section className="relative z-10 mt-10">
      <div className="mb-4 flex items-end justify-between">
        <h2 className="text-[18px] font-semibold">{title}</h2>
        <Link href={href} className="text-[12px] text-cy hover:underline">View all →</Link>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((p) => <PromptCard key={p.id} prompt={p} />)}
      </div>
    </section>
  );
}
