"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";
import { GovBadges } from "../../components/Badges";

export default function Approvals() {
  const [queue, setQueue] = useState<any[] | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [notes, setNotes] = useState<Record<string, string>>({});

  const load = () => api.approvals().then(setQueue).catch((e) => setErr(e.status === 403 ? "forbidden" : e.status === 401 ? "auth" : e.message));
  useEffect(() => { load(); }, []);

  if (err === "auth") return <Note title="Sign in required" body="Open ZoidLab from your Nyquest app to sign in." />;
  if (err === "forbidden") return <Note title="Reviewers only" body="The approval queue is restricted to Prompter admins." />;
  if (!queue) return <div className="py-24 text-center text-faint">Loading…</div>;

  async function act(a: any, decision: "approve" | "reject" | "request-changes") {
    setBusy(a.id + decision);
    try { await api.review(a.id, decision, notes[a.id] || ""); load(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(""); }
  }

  return (
    <div className="py-8">
      <h1 className="text-[22px] font-semibold">Approval queue</h1>
      <p className="mt-1 text-[13px] text-dim">Review prompts submitted for production. Approving marks the prompt approved-for-production.</p>
      {!queue.length ? <Note title="Queue is empty" body="No prompts are pending approval." /> : (
        <div className="mt-6 space-y-4">
          {queue.map((a) => (
            <div key={a.id} className="rounded-2xl border border-line bg-panel p-5">
              <div className="flex flex-wrap items-center gap-3">
                <Link href={`/prompts/${a.prompt_id}`} className="text-[15px] font-semibold text-ink hover:text-cy">{a.prompt_name}</Link>
                <span className="rounded bg-white/5 px-1.5 py-0.5 text-[11px] text-dim">{a.category}</span>
                <span className="text-[11px] text-faint">submitted {a.submitted_at?.slice(0, 16).replace("T", " ")}</span>
              </div>
              <p className="mt-1 text-[13px] text-dim">{a.description}</p>
              <div className="mt-2"><GovBadges badges={a.badges} /></div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input value={notes[a.id] || ""} onChange={(e) => setNotes({ ...notes, [a.id]: e.target.value })} placeholder="Reviewer notes (optional)"
                  className="min-w-[200px] flex-1 rounded-lg border border-line bg-panel2 px-3 py-2 text-[12px] text-ink outline-none focus:border-vi/60" />
                <Link href={`/prompts/${a.prompt_id}/test`} className="rounded-lg border border-line px-3 py-2 text-[12px] text-dim hover:text-ink">Test</Link>
                <button onClick={() => act(a, "approve")} disabled={!!busy} className="rounded-lg bg-ok/90 px-4 py-2 text-[12px] font-semibold text-white hover:opacity-90 disabled:opacity-50">Approve</button>
                <button onClick={() => act(a, "request-changes")} disabled={!!busy} className="rounded-lg border border-line px-3 py-2 text-[12px] text-ink hover:bg-white/5 disabled:opacity-50">Request changes</button>
                <button onClick={() => act(a, "reject")} disabled={!!busy} className="rounded-lg border border-bad/40 px-3 py-2 text-[12px] text-bad hover:bg-bad/10 disabled:opacity-50">Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Note({ title, body }: { title: string; body: string }) {
  return <div className="py-16 text-center"><div className="text-[15px] text-dim">{title}</div><div className="mt-1 text-[13px] text-faint">{body}</div></div>;
}
