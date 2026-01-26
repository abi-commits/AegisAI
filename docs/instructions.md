# AegisAI — Implementation & Execution Guide

This document is the **single source of truth** for building AegisAI. It defines *what to build, how to build it, and why each decision exists*. Treat this like an internal engineering design + execution manual.

---

## 1. System Objective (Non‑Negotiable)

AegisAI is an **agentic fraud & trust intelligence system** for detecting Account Takeover (ATO) while preserving:

* Explainability
* Human authority
* Auditability
* Operational safety

The system must:

* Detect suspicious logins
* Decide *whether AI is allowed to decide*
* Escalate uncertainty to humans
* Log every decision immutably

Accuracy alone is insufficient.

---

## 2. Core Design Principles

1. **No Single Model Authority**
   Decisions emerge from multiple bounded agents.

2. **Confidence Gating**
   AI may refuse to act.

3. **Human Override Is Final**
   AI decisions are suggestions, not verdicts.

4. **Explainability Is Mandatory**
   Every action must have a human‑readable reason.

5. **Governance First**
   Policies constrain AI behavior at runtime.

---

## 3. Tech Stack (Opinionated & Minimal)

### Language & Runtime

* **Python 3.13** — ecosystem maturity, ML tooling

### Data & Validation

* **Pydantic** — schema enforcement
* **Pandas / NumPy** — feature processing

### Models

* **XGBoost / LightGBM** — tabular fraud detection
* **Scikit‑learn** — behavioral distance models, calibration
* **Graph Neural Network** PyTorch Geometric — lightweight GNN

### Explainability

* **SHAP** — feature attribution
* Rule‑based explanation templates (no LLM hallucination)

### Orchestration

* Native Python (async where needed)
* Explicit agent router (no black‑box frameworks)

### Governance & Config

* **YAML** — policy rules
* **JSONL** — audit logs

### API (Optional)

* **FastAPI** — inference endpoint

### MLOps (Lightweight)

* **MLflow** — model & experiment tracking
* **GitHub Actions** — CI

---

## 4. Repository Structure (Frozen)

```
aegis-ai/
│
├── agents/
│   ├── detection_agent/
│   ├── behavior_agent/
│   ├── network_agent/
│   ├── confidence_agent/
│   └── explanation_agent/
│
├── data/
│   ├── schemas/
│   ├── validators/
│   └── generators/
│
├── models/
│   ├── risk_models/
│   ├── graph_models/
│   └── calibration/
│
├── orchestration/
│   ├── agent_router.py
│   └── decision_flow.py
│
├── governance/
│   ├── audit_logger.py
│   ├── policy_rules.yaml
│   └── versioning.py
│
├── evaluation/
│   ├── false_positive_analysis.py
│   └── human_override_metrics.py
│
├── api/
│   └── inference_service.py
│
├── docs/
│   ├── architecture.md
│   ├── decision_lifecycle.md
│   └── failure_cases.md
│
├── README.md
└── pyproject.toml
```

---

## 5. Canonical Data Schemas

### User

* user_id: str
* account_age_days: int
* home_country: str

### Device

* device_id: str (hashed)
* device_type: str
* os: str
* browser: str

### Session

* session_id: str
* user_id: str
* device_id: str
* ip_address: str
* geo_location: str
* start_time: datetime

### LoginEvent

* event_id: str
* session_id: str
* timestamp: datetime
* success: bool

### RiskDecision

* decision_id: str
* session_id: str
* final_action: enum
* confidence_score: float
* explanation_text: str
* human_review: bool

All schemas must be validated before processing.

---

## 6. Agent Contracts (Strict)

### Detection Agent

* **Input:** LoginEvent + session features
* **Output:** risk_signal_score, risk_factors
* **Cannot:** block or decide

### Behavioral Agent

* **Input:** session behavior vectors
* **Output:** behavioral_match_score
* **Cannot:** use network data

### Network Agent

* **Input:** user‑device‑IP graph slice
* **Output:** network_risk_score, evidence_links
* **Cannot:** act alone

### Confidence Agent

* **Input:** all agent outputs
* **Output:** decision_permission, final_confidence
* **Cannot:** label fraud

### Explanation Agent

* **Input:** approved decision + evidence
* **Output:** final_action, explanation_text, audit_log
* **Cannot:** override confidence gate

---

## 7. Decision Lifecycle

1. LoginEvent ingested
2. Detection, Behavioral, Network agents run in parallel
3. Signals aggregated
4. Confidence agent evaluates uncertainty
5. Decision fork:

   * AI allowed → action
   * AI denied → human review
6. Audit log written immutably

---

## 8. Policy Rules (Runtime Constraints)

Policies live in `policy_rules.yaml`.

Examples:

* AI cannot permanently block accounts
* Confidence < threshold → human review
* High disagreement → escalation

Policies must be evaluated **before actions execute**.

---

## 9. Evaluation Metrics

### Fraud Metrics

* ATO detection rate
* Loss prevented (simulated)

### Customer Impact

* False positive rate
* Step‑up frequency

### Decision Quality

* Human override rate
* Calibration error

### Governance

* % decisions auditable
* Policy violations

---

## 10. Failure Case Documentation

Each failure case must include:

* Description
* Root cause
* Affected agent
* Mitigation
* Escalation strategy

Failure cases are features, not bugs.

---

## 11. Execution Order (Mandatory)

1. Repo scaffold
2. Synthetic data generator
3. Agent skeletons (rules)
4. Orchestration flow
5. Minimal models
6. Policy enforcement
7. Demo scenario

Do not reorder.

---

## 12. Definition of Done

AegisAI is considered complete when:

* One end‑to‑end ATO scenario runs
* AI refuses to decide under uncertainty
* Human override is logged
* Explanation is generated
* Audit log is reproducible

Anything beyond this is optional.

---

This document must evolve **only when design decisions change**, not during experimentation.
