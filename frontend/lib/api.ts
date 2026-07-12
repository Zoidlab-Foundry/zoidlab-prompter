import type { Prompt, Project, Stats, WhoAmI, TestCase, RunResult, Version } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init, credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { detail = (await r.json()).detail || detail; } catch {}
    const e = new Error(detail) as Error & { status?: number }; e.status = r.status; throw e;
  }
  return r.json();
}
const qs = (q: Record<string, string>) => {
  const s = new URLSearchParams(Object.entries(q).filter(([, v]) => v)).toString();
  return s ? "?" + s : "";
};

export const api = {
  whoami: () => req<WhoAmI>("/api/whoami"),
  stats: () => req<Stats>("/api/stats"),
  filters: () => req<{ categories: any[]; statuses: any[]; risks: any[] }>("/api/filters"),
  models: () => req<{ models: string[]; featured: string[]; live: boolean }>("/api/models"),

  projects: () => req<{ projects: Project[] }>("/api/projects").then((d) => d.projects),
  project: (id: string) => req<Project & { prompts: Prompt[] }>(`/api/projects/${id}`),
  createProject: (b: any) => req<{ ok: boolean; project: Project }>("/api/projects", { method: "POST", body: JSON.stringify(b) }),

  prompts: (q: Record<string, string> = {}) => req<{ prompts: Prompt[]; count: number }>(`/api/prompts${qs(q)}`),
  prompt: (id: string) => req<Prompt>(`/api/prompts/${id}`),
  createPrompt: (b: any) => req<{ ok: boolean; prompt: Prompt }>("/api/prompts", { method: "POST", body: JSON.stringify(b) }),
  updatePrompt: (id: string, b: any) => req<{ ok: boolean; prompt: Prompt }>(`/api/prompts/${id}`, { method: "PUT", body: JSON.stringify(b) }),
  clonePrompt: (id: string) => req<{ ok: boolean; prompt: Prompt }>(`/api/prompts/${id}/clone`, { method: "POST" }),

  versions: (id: string) => req<{ versions: Version[] }>(`/api/prompts/${id}/versions`).then((d) => d.versions),
  saveVersion: (id: string, version: string, changelog: string) =>
    req<{ ok: boolean; versions: Version[] }>(`/api/prompts/${id}/versions`, { method: "POST", body: JSON.stringify({ version, changelog }) }),
  restoreVersion: (id: string, vid: string) => req<{ ok: boolean; prompt: Prompt }>(`/api/prompts/${id}/versions/${vid}/restore`, { method: "POST" }),
  diff: (id: string, vid: string, against?: string) => req<any>(`/api/prompts/${id}/versions/${vid}/diff${against ? "?against=" + against : ""}`),

  render: (id: string, variables: any) => req<any>(`/api/prompts/${id}/render`, { method: "POST", body: JSON.stringify({ variables }) }),
  test: (id: string, b: any) => req<RunResult>(`/api/prompts/${id}/test`, { method: "POST", body: JSON.stringify(b) }),
  compare: (id: string, b: any) => req<{ rendered: any; results: RunResult[] }>(`/api/prompts/${id}/compare`, { method: "POST", body: JSON.stringify(b) }),
  testRuns: (id: string) => req<{ runs: any[] }>(`/api/prompts/${id}/test-runs`).then((d) => d.runs),

  testCases: (id: string) => req<{ test_cases: TestCase[] }>(`/api/prompts/${id}/test-cases`).then((d) => d.test_cases),
  createTestCase: (id: string, b: any) => req<{ ok: boolean; test_case: TestCase }>(`/api/prompts/${id}/test-cases`, { method: "POST", body: JSON.stringify(b) }),
  deleteTestCase: (tid: string) => req<{ ok: boolean }>(`/api/test-cases/${tid}`, { method: "DELETE" }),

  submitApproval: (id: string) => req<{ ok: boolean }>(`/api/prompts/${id}/submit-approval`, { method: "POST" }),
  approvals: () => req<{ approvals: any[] }>("/api/approvals").then((d) => d.approvals),
  review: (aid: string, decision: "approve" | "reject" | "request-changes", notes = "") =>
    req<{ ok: boolean }>(`/api/approvals/${aid}/${decision}`, { method: "POST", body: JSON.stringify({ notes }) }),

  templates: () => req<{ templates: Prompt[] }>("/api/templates").then((d) => d.templates),
  useTemplate: (tid: string, projectId?: string) =>
    req<{ ok: boolean; prompt: Prompt }>(`/api/templates/${tid}/use${projectId ? "?project_id=" + projectId : ""}`, { method: "POST" }),

  audit: (id: string) => req<{ audit: any[] }>(`/api/prompts/${id}/audit`).then((d) => d.audit),
  exportJsonUrl: (id: string) => `/api/prompts/${id}/export/json`,
  exportMdUrl: (id: string) => `/api/prompts/${id}/export/markdown`,
};
