"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "../../lib/api";
import type { Prompt, Project } from "../../lib/types";
import PromptCard from "../../components/PromptCard";
import { CATEGORIES } from "../../lib/ui";

const STATUSES = ["all", "draft", "testing", "pending_approval", "approved", "deployed", "deprecated"];
const RISKS = ["all", "low", "medium", "high"];
const SORTS = [["updated", "Recently updated"], ["newest", "Newest"], ["approved", "Approved first"], ["name", "A–Z"]];

function Library() {
  const params = useSearchParams();
  const router = useRouter();
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState({
    search: "", project_id: "", category: "all", status: params.get("status") || "all",
    risk_level: "all", sort: "updated",
  });
  const [newOpen, setNewOpen] = useState(params.get("new") === "1");

  useEffect(() => { api.projects().then(setProjects).catch(() => {}); }, []);
  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      api.prompts({ search: f.search, project_id: f.project_id, category: f.category, status: f.status, risk_level: f.risk_level, sort: f.sort })
        .then((d) => setPrompts(d.prompts)).catch(() => setPrompts([])).finally(() => setLoading(false));
    }, 160);
    return () => clearTimeout(t);
  }, [f]);
  const set = (k: string, v: string) => setF((s) => ({ ...s, [k]: v }));

  return (
    <div className="py-8">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-[22px] font-semibold">Prompt Library</h1>
          <p className="mt-1 text-[13px] text-dim">Every prompt asset — versioned, tested, governed, deployable.</p>
        </div>
        <button onClick={() => setNewOpen(true)} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">Create Prompt</button>
      </div>

      <div className="mb-5 flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input value={f.search} onChange={(e) => set("search", e.target.value)} placeholder="Search prompts…"
            className="flex-1 rounded-xl border border-line bg-panel px-3 py-2.5 text-[13px] text-ink placeholder-faint outline-none focus:border-vi/60" />
          <select value={f.project_id} onChange={(e) => set("project_id", e.target.value)} className={sel}>
            <option value="">All projects</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select value={f.sort} onChange={(e) => set("sort", e.target.value)} className={sel}>
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="flex flex-wrap gap-2">
          <select value={f.category} onChange={(e) => set("category", e.target.value)} className={sel}>
            <option value="all">All categories</option>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select value={f.status} onChange={(e) => set("status", e.target.value)} className={sel}>
            {STATUSES.map((s) => <option key={s} value={s}>{s === "all" ? "All statuses" : s.replace("_", " ")}</option>)}
          </select>
          <select value={f.risk_level} onChange={(e) => set("risk_level", e.target.value)} className={sel}>
            {RISKS.map((r) => <option key={r} value={r}>{r === "all" ? "All risk" : r + " risk"}</option>)}
          </select>
        </div>
      </div>

      <div className="mb-3 text-[12px] text-faint">{loading ? "Loading…" : `${prompts.length} prompt${prompts.length === 1 ? "" : "s"}`}</div>
      {prompts.length === 0 && !loading ? (
        <div className="rounded-2xl border border-dashed border-line py-16 text-center text-[13px] text-faint">No prompts match. Create one to get started.</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {prompts.map((p) => <PromptCard key={p.id} prompt={p} />)}
        </div>
      )}

      {newOpen && <NewPrompt projects={projects} onClose={() => setNewOpen(false)} onCreated={(id) => router.push(`/prompts/${id}/edit`)} />}
    </div>
  );
}

function NewPrompt({ projects, onClose, onCreated }: { projects: Project[]; onClose: () => void; onCreated: (id: string) => void }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("General");
  const [project_id, setProject] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function create() {
    if (!name.trim()) return;
    setBusy(true); setErr("");
    try {
      const r = await api.createPrompt({ name, category, project_id: project_id || undefined,
        system_prompt: "You are a helpful assistant for {{business_name}}.", user_prompt: "{{user_message}}" });
      onCreated(r.prompt.id);
    } catch (e: any) { setErr(e.status === 401 ? "Sign in with your Nyquest account to create prompts." : e.message); setBusy(false); }
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl border border-line bg-panel2 p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-4 text-[16px] font-semibold">Create prompt</h2>
        <label className="mb-3 block"><span className="mb-1 block text-[12px] text-faint">Name</span>
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Restaurant Concierge" className={inp} /></label>
        <div className="mb-3 grid grid-cols-2 gap-3">
          <label><span className="mb-1 block text-[12px] text-faint">Category</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)} className={inp}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></label>
          <label><span className="mb-1 block text-[12px] text-faint">Project</span>
            <select value={project_id} onChange={(e) => setProject(e.target.value)} className={inp}><option value="">None</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        </div>
        {err && <p className="mb-3 text-[12px] text-bad">{err}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-line px-4 py-2 text-[13px] text-dim hover:text-ink">Cancel</button>
          <button onClick={create} disabled={busy || !name.trim()} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{busy ? "Creating…" : "Create & edit"}</button>
        </div>
      </div>
    </div>
  );
}

const sel = "rounded-xl border border-line bg-panel px-3 py-2.5 text-[13px] text-dim outline-none focus:border-vi/60";
const inp = "w-full rounded-xl border border-line bg-panel px-3 py-2.5 text-[13px] text-ink outline-none focus:border-vi/60";

export default function PromptsPage() {
  return <Suspense fallback={<div className="py-16 text-center text-faint">Loading…</div>}><Library /></Suspense>;
}
