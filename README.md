# AegisAI

### Agentic Fraud & Trust Intelligence System

AegisAI is an agentic AI system for Account Takeover (ATO) detection in digital banking and fintech environments. Unlike traditional fraud systems that optimize for detection accuracy, AegisAI treats **trust as a system-level property** rather than a model metric.

---

## Table of Contents

1. [What AegisAI Is](#what-aegisai-is)
2. [Why Accuracy Is Not Enough](#why-accuracy-is-not-enough)
3. [Architecture & Agents](#architecture--agents)
4. [Decision Lifecycle](#decision-lifecycle)
5. [Governance & Safety](#governance--safety)
6. [Demo Walkthrough](#demo-walkthrough)
7. [Known Limitations](#known-limitations)
8. [Future Extensions](#future-extensions)

---

## What AegisAI Is

AegisAI is a **governed decision-making system** for detecting account takeover fraud. It consists of:

- **5 specialized agents** that analyze login events from different perspectives
- **A confidence gating mechanism** that determines when AI should decide vs. escalate
- **An immutable audit system** that logs every decision with full traceability
- **Policy constraints** that override model outputs when necessary
- **Human-in-the-loop integration** for edge cases and uncertainty

AegisAI processes login events and produces one of four outcomes:
- `ALLOW` — Legitimate user, proceed silently
- `CHALLENGE` — Suspicious signals, require step-up authentication
- `BLOCK` — High-confidence fraud, deny access
- `ESCALATE` — Uncertain, defer to human reviewer

The system is designed for **high-stakes decisions** where false positives harm legitimate users and false negatives enable fraud.

---

## Why Accuracy Is Not Enough

Traditional fraud systems are evaluated on detection accuracy. This is insufficient for production deployment:


### What Actually Matters

AegisAI tracks metrics that reflect real-world impact:

| Metric | What It Measures | Target |
|--------|------------------|--------|
| **False Positive Rate** | How often legitimate users are harmed | < 5% |
| **Escalation Rate** | How often AI exercises restraint | 5-30% |
| **Human Override Rate** | How often humans change AI decisions | < 20% |
| **Confidence Calibration Error** | How honest AI is about uncertainty | < 0.10 |
| **Policy Violation Count** | How often hard limits are breached | **0** |

A system with 99% accuracy that blocks 10% of legitimate users is worse than one with 95% accuracy that escalates edge cases to humans.

---

## Architecture & Agents

AegisAI uses a **multi-agent architecture** where no single model has decision authority.

### Agent Overview

```
                         ┌─────────────────┐
                         │  Login Event    │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
              ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
              │ Detection │ │ Behavior  │ │ Network   │
              │   Agent   │ │   Agent   │ │   Agent   │
              └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
                    │             │             │
                    └─────────────┼─────────────┘
                                  │
                         ┌────────▼────────┐
                         │   Confidence    │
                         │     Agent       │
                         │  (GATEKEEPER)   │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │   Explanation   │
                         │     Agent       │
                         └────────┬────────┘
                                  │
               ┌──────────────────┼──────────────────┐
               │                  │                  │
        ┌──────▼──────┐   ┌───────▼───────┐   ┌──────▼──────┐
        │    ALLOW    │   │   CHALLENGE   │   │  ESCALATE   │
        │   (silent)  │   │  (step-up)    │   │  (human)    │
        └─────────────┘   └───────────────┘   └─────────────┘
```


---

## Decision Lifecycle

Every login event follows this immutable lifecycle:

### Phase 1: Input Validation
```
LoginEvent + Session + Device + User → InputContext (frozen)
```
All input is validated through Pydantic schemas. Invalid input is rejected before processing.

### Phase 2: Parallel Agent Analysis
```
InputContext → [Detection, Behavior, Network] → AgentOutputs
```
Three analysis agents run in parallel. Each produces a risk score and supporting evidence.

### Phase 3: Confidence Gating (THE SACRED CHECK)
```
AgentOutputs → ConfidenceAgent → decision_permission
```
The Confidence Agent determines whether AI should decide:
- `AI_ALLOWED` — Agents agree, confidence is high, proceed to action
- `HUMAN_REQUIRED` — Disagreement too high, escalate to human

**This is the most important component.** The confidence gate enforces AI restraint.

### Phase 4: Action or Escalation
```
If AI_ALLOWED:    AgentOutputs → ExplanationAgent → FinalDecision
If HUMAN_REQUIRED: AgentOutputs → EscalationCase → Human Queue
```

### Phase 5: Audit Logging
```
FinalDecision | EscalationCase → AuditLogger → JSONL (immutable)
```
Every decision is logged with full traceability. Logs are append-only with hash-chain integrity.

### Context Immutability

The `DecisionContext` is a frozen dataclass. Once created, nothing can modify it:
```python
@dataclass(frozen=True)
class DecisionContext:
    context_id: str
    created_at: datetime
    input_context: InputContext
    agent_outputs: Optional[AgentOutputs]
    final_decision: Optional[FinalDecision]
    escalation_case: Optional[EscalationCase]
```

This ensures complete auditability and prevents post-hoc tampering.

---

## Governance & Safety

AegisAI enforces governance at multiple levels.

### Policy Constraints

Hard limits that cannot be overridden by models:

```yaml
confidence:
  min_to_allow: 0.80        # AI needs 80%+ confidence to decide
  min_to_escalate: 0.50     # Below 50% always escalates

actions:
  permanent_block_allowed: false  # AI cannot permanently block
  human_only_actions:
    - "BLOCK_PERMANENT"
    - "ACCOUNT_TERMINATION"
    - "LEGAL_HOLD"

escalation:
  disagreement_threshold: 0.30    # >30% disagreement → human
  consecutive_high_risk_limit: 3  # 3+ high-risk → human
```

### Human Override System

When AI escalates, humans can:
- `APPROVE` — Allow the login
- `REJECT` — Block the login
- `MODIFY` — Take a different action
- `DEFER` — Escalate further

All overrides are logged immutably with:
- Reviewer ID and role
- Reason for override
- Original AI recommendation
- Policy version at time of decision

### Audit Trail

Every decision produces an audit entry:

```json
{
  "entry_id": "aud_abc123def456",
  "timestamp": "2026-01-27T10:30:00Z",
  "event_type": "decision",
  "decision_id": "dec_xyz789",
  "action": "ESCALATE",
  "decided_by": "HUMAN_REQUIRED",
  "confidence_score": 0.62,
  "policy_version": "1.0.0",
  "agent_outputs": { ... },
  "previous_hash": "sha256:...",
  "entry_hash": "sha256:..."
}
```

Audit logs use hash-chain integrity. Any tampering breaks the chain.

---

## Deployment

For production deployment to AWS ECS, see [deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md).

---

## Known Limitations

- Confidence calibration is heuristic-based; re-calibrate on real data
- Agents run sequentially; parallel execution in future versions
- No A/B testing framework yet; use separate evaluation suite
- Time: 3:15 AM local time
- Failed attempts: 2 before success

**Output:**
```
Decision: CHALLENGE
Decided by: AI
Confidence: 78%
```

The user is prompted for step-up authentication (SMS code, etc.).

### Scenario 3: Ambiguous Login → ESCALATE (THE STAR)

A login from a new mobile device in London. Could be legitimate travel or ATO.

**Input:**
- User: Same account
- Device: New iPhone (could be new phone)
- Location: London, UK (no VPN)
- Time: 2:30 PM local (normal hours)
- Behavior: Partially matches (mobile vs. desktop)

**Output:**
```
Decision: ESCALATE
Decided by: HUMAN_REQUIRED
Confidence: 62%
Reason: HIGH_DISAGREEMENT
```

The AI refuses to decide. A human fraud analyst reviews the case, checks travel history, and approves the login.

> **"The most important decision this system makes is knowing when not to decide."**

### Running the Evaluation Suite

```bash
# Standard evaluation: 100 legit + 20 ATO
python -m src.aegis_ai.evaluation.runner

# Quick evaluation: 20 legit + 5 ATO
python -m src.aegis_ai.evaluation.runner --quick

# Custom configuration
python -m src.aegis_ai.evaluation.runner --legit 200 --ato 50 --seed 123
```

---

## Known Limitations

AegisAI is a demonstration system with deliberate constraints:

### Data Limitations
- **Synthetic data only** — No real customer data is used
- **Simplified behavioral signals** — Real systems have richer biometrics
- **Limited geographic coverage** — 10 countries in the generator

### Model Limitations
- **No online learning** — Models are static, not continuously updated
- **Lightweight graph modeling** — Production would use deeper GNNs
- **No ensemble calibration** — Single calibration method (isotonic)

### Operational Limitations
- **No streaming ingestion** — Batch processing only
- **No real-time monitoring** — Evaluation is post-hoc
- **No A/B testing framework** — Static policy rules

These limitations are **intentional** to keep the system:
- Auditable (no hidden state)
- Reproducible (deterministic seeds)
- Understandable (no black-box ensembles)

---

## Future Extensions

AegisAI could be extended with:

### Near-Term
- **Streaming ingestion** — Kafka/Kinesis integration
- **Real-time monitoring** — Prometheus metrics, Grafana dashboards
- **API service** — FastAPI endpoint for inference

### Medium-Term
- **Richer behavioral biometrics** — Typing patterns, mouse dynamics
- **Advanced graph reasoning** — Temporal knowledge graphs
- **Online policy learning** — Contextual bandits for threshold tuning

### Long-Term
- **Federated learning** — Cross-institution fraud patterns
- **Causal inference** — Understanding fraud dynamics
- **Explainable escalation** — Natural language case summaries

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/abi-commits/AegisAI.git
cd AegisAI

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"
```

### Run the Demo

```bash
python demo.py
```

### Run the Evaluation

```bash
python -m src.aegis_ai.evaluation.runner
```

### Run Tests

```bash
pytest tests/ -v
```

---

## Contact

For questions about this system design, please open an issue on GitHub.
