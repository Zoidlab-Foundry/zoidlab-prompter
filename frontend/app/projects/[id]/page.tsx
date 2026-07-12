"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "../../../lib/api";
import type { Prompt, Project } from "../../../lib/types";
import PromptCard from "../../../components/PromptCard";

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<(Project & { prompts: Prompt[] }) | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.project(id).then(setProject).catch((e) => setErr(e.message)); }, [id]);

  if (err) return <div className="py-24 text-center text-faint">{err}</div>;
  if (!project) return <div className="py-24 text-center text-faint">Loading…</div>;

  return (
    <div className="py-8">
      <Link href="/projects" className="text-[12px] text-faint hover:text-dim">← Projects</Link>
      <div className="mt-4 mb-6 flex items-center gap-4">
        <span className="grid h-14 w-14 place-items-center rounded-2xl text-[28px]" style={{ background: `${project.accent}22` }}>{project.icon}</span>
        <div>
          <h1 className="text-[24px] font-bold">{project.name}</h1>
          <p className="text-[13px] text-dim">{project.description}</p>
        </div>
        <Link href={`/prompts?new=1`} className="ml-auto rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">New Prompt</Link>
      </div>
      {project.prompts.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line py-16 text-center text-[13px] text-faint">No prompts in this project yet.</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {project.prompts.map((p) => <PromptCard key={p.id} prompt={p} />)}
        </div>
      )}
    </div>
  );
}
