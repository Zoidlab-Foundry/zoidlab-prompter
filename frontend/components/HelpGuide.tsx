"use client";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/* In-app guide: what Prompter is and how to take a prompt from draft to deployed API.
   Auto-opens once per browser (localStorage) and lives behind the Guide nav button. */

const STORAGE_KEY = "pr_guide_v1";

const STEPS: { title: string; body: string }[] = [
  {
    title: "Start from a template or scratch",
    body: "Templates are production-ready starting points — Use Template spins up a private, editable copy in your workspace. Or hit Create Prompt in the Prompt Library to begin from a blank slate.",
  },
  {
    title: "Edit with variables",
    body: "The editor splits your prompt into System, Developer, User, and Tools sections. Write {{variables}} anywhere — they're auto-detected — and set model settings, risk level, and governance alongside the copy.",
  },
  {
    title: "Prove it in the Test Lab",
    body: "Run the prompt across the Nyquest models you pick and compare output, cost, latency, and quality side by side. Live runs get an LLM-judged score with a rationale; mock runs cost nothing.",
  },
  {
    title: "Snapshot versions",
    body: "Save Version freezes an immutable snapshot with a changelog. Version history lets you diff any version against the previous one and restore to roll back — the rollback is itself versioned.",
  },
  {
    title: "Submit for approval",
    body: "Submit the prompt for production approval. Reviewers see it in the approval queue and can approve, reject, or request changes — approval marks it approved-for-production.",
  },
  {
    title: "Deploy as a live API",
    body: "Export & Deploy serves the prompt as a token-authed HTTP endpoint: POST variables, get the model's output. Or export it as a portable Nyquest Prompt Package and use it in Builder or Marketplace.",
  },
];

export default function HelpGuide() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch {}
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch {}
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") dismiss(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-dim transition hover:text-ink hover:bg-white/5"
        aria-label="Open the Prompter guide"
      >
        Guide
      </button>
      {open && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={dismiss} role="dialog" aria-modal="true" aria-label="Prompter guide">
          <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border border-line bg-panel p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-1 flex items-center gap-2">
              <span className="grid h-6 w-6 place-items-center rounded-md bg-vi/15 text-[13px] text-vi">◈</span>
              <h2 className="text-[16px] font-semibold">How Prompter works</h2>
            </div>
            <p className="mb-5 text-[13px] text-dim">
              Enterprise prompt lifecycle — versioned, tested, governed, deployable. Six steps from idea to live endpoint:
            </p>
            <ol className="space-y-4">
              {STEPS.map((s, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-vi/15 text-[12px] font-semibold text-vi">{i + 1}</span>
                  <div>
                    <div className="text-[13.5px] font-medium">{s.title}</div>
                    <div className="text-[12.5px] leading-relaxed text-dim">{s.body}</div>
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-6 flex items-center justify-between border-t border-line pt-4">
              <a href="https://foundry.zoidlab.ai" className="text-[12px] text-dim hover:text-ink">◈ All Foundry apps</a>
              <button onClick={dismiss} className="rounded-lg bg-vi px-4 py-1.5 text-[12.5px] font-semibold text-white hover:opacity-90">
                Got it
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
