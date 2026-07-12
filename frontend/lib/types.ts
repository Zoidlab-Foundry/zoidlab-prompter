export interface Variable {
  name: string; type: string; required?: boolean; description?: string;
  default?: string; example?: string;
}

export interface ModelSettings {
  provider: string; model: string; temperature: number; max_tokens: number;
  top_p?: number; json_mode?: boolean; streaming?: boolean; tool_calling?: boolean;
  fallback_model?: string; timeout_s?: number; retries?: number;
}

export interface Governance {
  risk_level: "low" | "medium" | "high"; sensitive_data?: boolean;
  pii_risk?: "low" | "medium" | "high"; external_api?: boolean;
  requires_human_approval?: boolean; logs_prompts?: boolean; logs_outputs?: boolean;
  approved_for_production?: boolean;
}

export interface Project {
  id: string; name: string; slug: string; description: string; status: string;
  icon: string; accent: string; owner_user_id?: string | null;
  prompt_count?: number; updated_at?: string;
}

export interface Version {
  id: string; version: string; changelog: string; status: string;
  created_by?: string; created_at: string;
}

export interface TestCase {
  id: string; name: string; description?: string; input_variables: Record<string, any>;
  expected_keywords: string[]; negative_keywords: string[]; notes?: string;
}

export interface Evaluation {
  clarity: number; accuracy: number; completeness: number; tone_match: number;
  safety: number; policy_compliance: number; json_validity: number;
  hallucination_risk: number; injection_resistance: number; keyword_match: number;
  overall: number; negative_keyword_hit?: boolean;
}

export interface RunResult {
  provider: string; label: string; model: string; output: string;
  metrics: { token_estimate: number; cost_estimate: number; latency_ms: number; quality_score: number; risk_score: number };
  evaluation: Evaluation; latency_ms: number; cost_estimate: number; token_estimate: number; run_id?: string;
}

export interface Prompt {
  id: string; name: string; slug: string; description: string; category: string;
  tags: string[]; status: string; risk_level: string; current_version: string;
  project_id?: string | null; owner_user_id?: string | null; template?: boolean;
  system_prompt?: string; developer_prompt?: string; user_prompt?: string; tool_prompt?: string;
  output_schema?: any; variables: Variable[]; model_settings: ModelSettings; governance: Governance;
  created_at?: string; updated_at?: string;
  badges?: string[]; versions?: Version[]; test_cases?: TestCase[];
  project?: Project | null; latest_runs?: any[];
}

export interface Stats {
  total: number; approved: number; draft: number; test_runs: number;
  avg_cost: number; avg_latency: number;
}

export interface WhoAmI { authenticated: boolean; email?: string; name?: string; tier?: string; admin?: boolean; }
