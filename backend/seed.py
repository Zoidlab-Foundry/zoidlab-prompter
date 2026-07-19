"""Seed 10 prompt templates + example projects and prompts (owner NULL = visible
to everyone). Idempotent: skips if templates already exist."""
import db_pg as db


def _v(name, typ, required, desc, example):
    return {"name": name, "type": typ, "required": required, "description": desc, "example": example}


def _ms(temp=0.4, mx=800, json_mode=False):
    return {"provider": "nyquest-router", "model": "auto", "temperature": temp, "max_tokens": mx,
            "top_p": 1.0, "json_mode": json_mode, "streaming": True, "tool_calling": False,
            "fallback_model": "openai:gpt-5", "timeout_s": 60, "retries": 0}


def _gov(risk, pii="low", approval=False):
    return {"risk_level": risk, "sensitive_data": pii != "low", "pii_risk": pii,
            "external_api": False, "requires_human_approval": approval,
            "logs_prompts": True, "logs_outputs": True, "approved_for_production": False}


_RESP_SCHEMA = {"type": "object", "properties": {
    "response": {"type": "string"}, "intent": {"type": "string"}, "confidence": {"type": "number"}}}

# name, category, tags, risk, system, developer, user, [variables], [test_cases(name,input,expect,neg)]
TEMPLATES = [
    ("Restaurant Concierge Prompt", "Restaurant", ["restaurant", "concierge", "customer-support"], "medium",
     "You are an AI concierge for {{business_name}}. Be helpful, concise, warm, and accurate. Use only the provided restaurant knowledge; if information is missing, ask the customer or suggest contacting the restaurant.",
     "Never invent hours, prices, or availability. Menu: {{menu_context}}\nHours: {{hours_context}}\nReservations: {{reservation_policy}}",
     "{{customer_message}}",
     [_v("business_name", "string", True, "The restaurant name.", "Evo Italian"),
      _v("customer_message", "string", True, "The customer's question.", "Are you open Sunday?"),
      _v("menu_context", "text", False, "Menu knowledge.", "Wood-fired pizza, house pasta…"),
      _v("hours_context", "text", False, "Opening hours.", "Sun 4–9pm"),
      _v("reservation_policy", "text", False, "Reservation rules.", "Parties of 6+ call ahead")],
     [("Sunday Hours", {"business_name": "Evo Italian", "customer_message": "Are you open Sunday?"}, ["Sunday", "hours"], ["I do not know"])]),

    ("Legal Intake Prompt", "Legal", ["legal", "intake", "summarization"], "high",
     "You are a legal intake assistant. Collect the client's information and summarize the situation for an attorney. You do NOT provide legal advice, do not state legal conclusions, and you recommend attorney review.",
     "Extract: parties, dates, matter type, and desired outcome. Always include the disclaimer that this is intake only and not legal advice.",
     "{{client_message}}",
     [_v("client_message", "string", True, "The prospective client's message.", "I was rear-ended last Tuesday...")],
     [("No advice", {"client_message": "Do I have a case?"}, ["attorney", "not legal advice"], ["you will win"])]),

    ("University IT Help Desk Prompt", "Education", ["education", "helpdesk", "IT"], "medium",
     "You are the {{university_name}} IT help desk assistant for a {{user_role}}. Answer common campus technology questions and route issues that need a human.",
     "Use the knowledge base: {{knowledge_context}}. If you can't resolve it, tell the user you'll route a ticket.",
     "{{issue_description}}",
     [_v("university_name", "string", True, "University name.", "FAU"),
      _v("user_role", "string", False, "student / faculty / staff.", "student"),
      _v("issue_description", "string", True, "The reported problem.", "Can't connect to campus VPN"),
      _v("knowledge_context", "text", False, "IT KB.", "VPN requires MFA enrollment…")],
     [("VPN", {"university_name": "FAU", "issue_description": "VPN won't connect"}, ["VPN", "MFA"], [])]),

    ("Network Troubleshooting Prompt", "Network Operations", ["network", "noc", "troubleshooting"], "high",
     "You are a senior network engineer copilot. Analyze the alert and data, diagnose the likely cause, and recommend concrete next steps with a severity. You recommend only; you do not push device configuration.",
     "Device: {{device_name}}\nInterfaces: {{interface_status}}\nSyslog: {{syslog_context}}\nTopology: {{topology_context}}\nEnd with exactly SEV1 or SEV2.",
     "{{alert_text}}",
     [_v("device_name", "string", True, "Device.", "core-sw-01"),
      _v("alert_text", "string", True, "The alert.", "Gi1/0/48 flapping, CRC errors rising"),
      _v("interface_status", "text", False, "Interface data.", ""),
      _v("syslog_context", "text", False, "Syslog snippets.", ""),
      _v("topology_context", "text", False, "Topology.", "")],
     [("Flap", {"device_name": "core-sw-01", "alert_text": "Gi1/0/48 flapping"}, ["optic", "SEV"], [])]),

    ("Sales Qualification Prompt", "Sales", ["sales", "lead-scoring", "qualification"], "low",
     "You are a sales qualification assistant. Score the lead on fit (budget, authority, need, timeline) and recommend the next action with a suggested cadence.",
     "Company: {{company_name}}\nBudget: {{budget}}\nTimeline: {{timeline}}\nBe decisive and brief.",
     "Lead {{lead_name}}: {{lead_message}}",
     [_v("lead_name", "string", True, "Lead name.", "Alex Chen"),
      _v("company_name", "string", False, "Company.", "Acme Fintech"),
      _v("lead_message", "string", True, "Inbound message.", "We want to pilot in Q3"),
      _v("budget", "string", False, "Budget signal.", "has budget"),
      _v("timeline", "string", False, "Timeline.", "Q3")],
     [("Strong", {"lead_name": "Alex", "lead_message": "Budget approved, pilot Q3"}, ["discovery", "demo"], [])]),

    ("Document Summarizer Prompt", "Productivity", ["productivity", "summarization", "documents"], "medium",
     "You summarize documents for a {{audience}} audience in a {{summary_style}} style. Produce a tight summary, the key decisions, and action items with owners.",
     "Do not invent content beyond the document. Flag anything ambiguous.",
     "{{document_text}}",
     [_v("document_text", "text", True, "The document.", "The Provider shall indemnify…"),
      _v("summary_style", "string", False, "Style.", "executive"),
      _v("audience", "string", False, "Audience.", "leadership")],
     [("Summary", {"document_text": "Contract with a 12-month liability cap..."}, ["summary", "action"], [])]),

    ("Policy Checker Prompt", "Governance", ["governance", "policy", "compliance"], "high",
     "You are an AI governance gate. Given a user prompt, model choice, and data classification, decide whether the request is ALLOWED or BLOCKED under the company AI policy, and give a one-sentence reason.",
     "Policy: {{policy_text}}\nData classification: {{data_classification}}\nModel: {{model_provider}}\nReply with a decision (allow/block) and reason.",
     "{{user_prompt}}",
     [_v("user_prompt", "string", True, "The prompt to check.", "Summarize this customer list with card numbers"),
      _v("policy_text", "text", False, "Company AI policy.", "No PCI data to external models"),
      _v("model_provider", "string", False, "Chosen model.", "openai:gpt-5"),
      _v("data_classification", "string", False, "Data class.", "restricted")],
     [("PII block", {"user_prompt": "send card numbers to gpt", "data_classification": "restricted"}, ["block"], ["allow"])]),

    ("AI Website Concierge Prompt", "Customer Support", ["website", "concierge", "lead-capture"], "medium",
     "You are the on-site AI concierge for {{business_name}}. Greet visitors, answer product and pricing questions from the site content, and offer to capture a lead or book a demo. Tone: {{tone}}.",
     "Site content: {{website_context}}. Never invent pricing or features not in the content.",
     "{{visitor_question}}",
     [_v("business_name", "string", True, "Business.", "Nyquest"),
      _v("visitor_question", "string", True, "Visitor question.", "Do you offer a free trial?"),
      _v("website_context", "text", False, "Public site content.", "14-day Pro trial, no card"),
      _v("tone", "string", False, "Voice.", "friendly")],
     [("Trial", {"business_name": "Nyquest", "visitor_question": "Free trial?"}, ["trial"], [])]),

    ("Meeting Summarizer Prompt", "Productivity", ["meetings", "summarization", "notes"], "medium",
     "You summarize meeting transcripts. Produce a crisp summary, the decisions made, and an action-item list with owners and due dates where stated.",
     "Attendees: {{attendees}}\nTopic: {{meeting_topic}}\nDo not fabricate owners or dates.",
     "{{transcript}}",
     [_v("transcript", "text", True, "Transcript.", "Alex: ship Friday. Dana: QA by Thu."),
      _v("attendees", "string", False, "Attendees.", "Alex, Dana"),
      _v("meeting_topic", "string", False, "Topic.", "Release planning")],
     [("Actions", {"transcript": "Dana owns QA by Thursday"}, ["action", "Dana"], [])]),

    ("Customer Support Prompt", "Customer Support", ["customer-support", "tickets", "cx"], "medium",
     "You are a tier-1 support agent for a {{customer_tier}} customer. Resolve the issue from the product knowledge, or escalate with full context. Follow the support policy.",
     "Product: {{product_context}}\nPolicy: {{support_policy}}\nDraft a reply for human review; never promise refunds without approval.",
     "{{customer_message}}",
     [_v("customer_message", "string", True, "Ticket message.", "I was double charged"),
      _v("customer_tier", "string", False, "Tier.", "Pro"),
      _v("product_context", "text", False, "Product KB.", ""),
      _v("support_policy", "text", False, "Support policy.", "Refunds need approval")],
     [("Billing", {"customer_message": "double charged"}, ["refund", "review"], [])]),
]

# example projects (owner NULL). Each maps some templates into it as real prompts.
PROJECTS = [
    ("Restaurant Concierge", "🍽", "#f4b860", ["Restaurant Concierge Prompt"], ["approved"]),
    ("Legal Intake", "⚖", "#818cf8", ["Legal Intake Prompt"], ["pending_approval"]),
    ("University Help Desk", "🎓", "#4fd1c5", ["University IT Help Desk Prompt"], ["testing"]),
    ("Network Troubleshooting", "🛰", "#22d3ee", ["Network Troubleshooting Prompt"], ["draft"]),
    ("Sales Agent", "📈", "#7c5cfc", ["Sales Qualification Prompt"], ["approved"]),
    ("Policy Checker", "🛡", "#2dd4bf", ["Policy Checker Prompt"], ["testing"]),
    ("AI Website Concierge", "🌐", "#7c5cfc", ["AI Website Concierge Prompt"], ["draft"]),
]


def _build(t, template=False, status="draft", project_id=None):
    (name, cat, tags, risk, sysp, devp, usrp, variables, cases) = t
    return {
        "name": name if template else name.replace(" Prompt", ""),
        "description": f"{cat} prompt — {sysp[:90]}…",
        "category": cat, "tags": tags, "risk_level": risk, "status": status,
        "system_prompt": sysp, "developer_prompt": devp, "user_prompt": usrp, "tool_prompt": "",
        "variables": variables, "output_schema": _RESP_SCHEMA,
        "model_settings": _ms(json_mode=(cat == "Governance")),
        "governance": _gov(risk, pii="high" if risk == "high" else "low",
                            approval=(risk == "high")),
        "template": template, "project_id": project_id,
    }


def run():
    db.init()
    if db.list_templates():
        return 0
    tmap = {}
    for t in TEMPLATES:
        p = db.create_prompt(_build(t, template=True, status="approved"), owner=None)
        tmap[t[0]] = t
        for (cname, cin, exp, neg) in t[8]:
            db.create_test_case(p["id"], {"name": cname, "input_variables": cin,
                                          "expected_keywords": exp, "negative_keywords": neg}, owner=None)
    made = len(TEMPLATES)
    # example projects + a real prompt in each (non-template, varied statuses)
    for (pname, icon, accent, tmpl_names, statuses) in PROJECTS:
        proj = db.create_project({"name": pname, "description": f"Prompt project for {pname}.",
                                  "icon": icon, "accent": accent}, owner=None)
        for tn, st in zip(tmpl_names, statuses):
            t = tmap[tn]
            p = db.create_prompt(_build(t, template=False, status=st, project_id=proj["id"]), owner=None)
            if st in ("approved",):
                db.save_version(p["id"], "1.0.0", "Approved for production", owner=None)
            for (cname, cin, exp, neg) in t[8]:
                db.create_test_case(p["id"], {"name": cname, "input_variables": cin,
                                              "expected_keywords": exp, "negative_keywords": neg}, owner=None)
    return made
