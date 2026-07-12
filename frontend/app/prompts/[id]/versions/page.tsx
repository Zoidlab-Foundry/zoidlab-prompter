"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "../../../../lib/api";
import type { Version } from "../../../../lib/types";

export default function Versions() {
  const { id } = useParams<{ id: string }>();
  const [versions, setVersions] = useState<Version[]>([]);
  const [diff, setDiff] = useState<any>(null);
  const [active, setActive] = useState<string>("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => api.versions(id).then(setVersions);
  useEffect(() => { load(); }, [id]);

  async function showDiff(v: Version) {
    setActive(v.id); setDiff(null);
    try { setDiff(await api.diff(id, v.id)); } catch (e: any) { setMsg(e.message); }
  }
  async function restore(v: Version) {
    setBusy(v.id); setMsg("");
    try { await api.restoreVersion(id, v.id); setMsg(`Restored v${v.version}.`); load(); }
    catch (e: any) { setMsg(e.status === 401 ? "Sign in required." : e.message); } finally { setBusy(""); }
  }

  return (
    <div className="py-8">
      <Link href={`/prompts/${id}`} className="text-[12px] text-faint hover:text-dim">← Prompt</Link>
      <h1 className="mt-3 text-[22px] font-semibold">Version history</h1>
      <p className="mt-1 text-[13px] text-dim">Every saved version is immutable. Restore to roll back — the rollback is itself versioned.</p>
      {msg && <div className="mt-3 rounded-lg border border-line bg-panel px-4 py-2 text-[13px] text-dim">{msg}</div>}

      <div className="mt-6 grid gap-4 lg:grid-cols-[340px_1fr]">
        <div className="space-y-2">
          {versions.map((v, i) => (
            <div key={v.id} className={`rounded-xl border p-3 ${active === v.id ? "border-vi/60 bg-vi/5" : "border-line bg-panel"}`}>
              <div className="flex items-center justify-between">
                <span className="text-[14px] font-semibold text-ink">v{v.version}</span>
                <span className="rounded-full border border-line px-2 py-0.5 text-[10px] text-faint">{v.status}</span>
              </div>
              <p className="mt-0.5 text-[12px] text-dim">{v.changelog}</p>
              <div className="mt-1 text-[11px] text-faint">{v.created_at?.slice(0, 16).replace("T", " ")}</div>
              <div className="mt-2 flex gap-2">
                <button onClick={() => showDiff(v)} className="rounded-md border border-line px-2.5 py-1 text-[11px] text-dim hover:text-ink">Diff</button>
                {i !== 0 && <button onClick={() => restore(v)} disabled={!!busy} className="rounded-md border border-line px-2.5 py-1 text-[11px] text-cy hover:bg-white/5 disabled:opacity-50">Restore</button>}
                <a href={`/api/versions/${v.id}`} target="_blank" rel="noopener" className="rounded-md border border-line px-2.5 py-1 text-[11px] text-dim hover:text-ink">Export</a>
              </div>
            </div>
          ))}
          {!versions.length && <p className="text-[13px] text-faint">No versions yet.</p>}
        </div>

        <div className="rounded-2xl border border-line bg-panel p-4">
          {!diff ? <p className="text-[13px] text-faint">Select a version and click <b>Diff</b> to compare it with the previous one.</p> : !diff.changed ? (
            <p className="text-[13px] text-faint">No differences from the previous version.</p>
          ) : (
            <div className="space-y-4">
              <div className="text-[12px] text-dim">Diff <b className="text-ink">v{diff.new_version}</b> vs <b className="text-ink">v{diff.old_version || "—"}</b></div>
              {Object.entries(diff.sections || {}).map(([sec, lines]: any) => (
                <div key={sec}>
                  <div className="mb-1 text-[11px] uppercase tracking-wider text-faint">{sec.replace("_", " ")}</div>
                  <pre className="overflow-auto rounded-lg border border-line bg-panel2 p-2 text-[12px] leading-relaxed">
                    {lines.map((l: any, i: number) => <div key={i} className={l.op === "add" ? "bg-ok/10 text-ok" : l.op === "del" ? "bg-bad/10 text-bad" : "text-dim"}>{l.op === "add" ? "+ " : l.op === "del" ? "- " : "  "}{l.text}</div>)}
                  </pre>
                </div>
              ))}
              {(diff.fields || []).map((f: any) => (
                <div key={f.field}>
                  <div className="mb-1 text-[11px] uppercase tracking-wider text-faint">{f.field.replace("_", " ")} changed</div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <pre className="overflow-auto rounded bg-bad/10 p-2 text-bad">{JSON.stringify(f.old, null, 1)}</pre>
                    <pre className="overflow-auto rounded bg-ok/10 p-2 text-ok">{JSON.stringify(f.new, null, 1)}</pre>
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
