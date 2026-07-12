export const RISK_STYLE: Record<string, string> = {
  low: "text-ok border-ok/40 bg-ok/10",
  medium: "text-warn border-warn/40 bg-warn/10",
  high: "text-bad border-bad/40 bg-bad/10",
};

export const STATUS_STYLE: Record<string, string> = {
  draft: "text-dim border-line bg-white/5",
  testing: "text-ind border-ind/40 bg-ind/10",
  pending_approval: "text-warn border-warn/40 bg-warn/10",
  approved: "text-ok border-ok/40 bg-ok/10",
  deployed: "text-cy border-cy/40 bg-cy/10",
  deprecated: "text-faint border-line bg-white/5",
  archived: "text-faint border-line bg-white/5",
};

export const STATUS_LABEL: Record<string, string> = {
  draft: "Draft", testing: "Testing", pending_approval: "Pending Approval",
  approved: "Approved", deployed: "Deployed", deprecated: "Deprecated", archived: "Archived",
};

export const BADGE_STYLE: Record<string, string> = {
  "Low Risk": RISK_STYLE.low, "Medium Risk": RISK_STYLE.medium, "High Risk": RISK_STYLE.high,
  "Approved": "text-ok border-ok/40 bg-ok/10", "Needs Review": "text-warn border-warn/40 bg-warn/10",
  "PII Risk": "text-bad border-bad/40 bg-bad/10", "Output Must Be JSON": "text-ind border-ind/40 bg-ind/10",
  "Human Approval Required": "text-vi border-vi/40 bg-vi/10", "External API": "text-cy border-cy/40 bg-cy/10",
};

export const CATEGORIES = [
  "Restaurant", "Legal", "Medical", "Education", "Network Operations", "Finance",
  "Sales", "Customer Support", "Marketing", "HR", "Security", "Developer Tools",
  "Research", "Productivity", "Governance", "General",
];
