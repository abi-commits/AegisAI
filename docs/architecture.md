# System Architecture — AegisAI

AegisAI employs a **multi-agent, parallel-execution architecture** designed to handle the complexity and high stakes of fraud detection. This document details the structural design and interaction patterns of the system.

---

## 1. Architectural Philosophy

The architecture is built on four core principles:
- **Separation of Concerns**: Risk prediction is decoupled from decision-making.
- **Explicit Uncertainty**: AI must quantify its confidence before acting.
- **Authority Gating**: Decisions are governed by deterministic policies and human oversight.
- **Immutability**: Every state change in the decision lifecycle is recorded permanently.

---

## 2. Decision Lifecycle

Every login event processed by AegisAI follows a strictly governed lifecycle:

1.  **Validation**: Incoming `LoginEvent` is validated against Pydantic schemas.
2.  **Parallel Analysis**: The `AgentRouter` executes the Detection, Behavior, and Network agents in parallel.
3.  **Synthesis**: Results are aggregated into an `AgentOutputs` collection.
4.  **Confidence Gate**: The `ConfidenceAgent` evaluates the outputs to determine if AI is allowed to decide.
5.  **Action Selection**: If allowed, the `ExplanationAgent` selects an action and generates a reasoning string.
6.  **Policy Enforcement**: The `PolicyEngine` validates the proposed action against hard-coded safety rules.
7.  **Audit Commitment**: The `UnifiedAuditTrail` writes the final decision to S3 and DynamoDB.

---

## 3. Agent Reasoning Layer

### Detection Agent
- **Purpose**: Identify tabular anomalies in login metadata.
- **Core Model**: XGBoost / LightGBM.
- **Constraint**: Cannot access relational data or previous user history in this scope.

### Behavioral Agent
- **Purpose**: Compare current session dynamics with historical user baselines.
- **Core Model**: Isolation Forest / LSTM.
- **Output**: A behavioral match score indicating consistency.

### Network Agent
- **Purpose**: Surface relational risk via shared devices, IPs, and entities.
- **Core Model**: Graph Neural Network (GNN).
- **Evidence**: Shared infrastructure links and known-bad clusters.

### Confidence Agent (The Gatekeeper)
- **Purpose**: Determine if the system is "certain" enough to make an autonomous decision.
- **Logic**: Evaluates agent agreement and individual model confidence scores.
- **Decision Permission**: `AI_ALLOWED` or `HUMAN_REQUIRED`.

### Explanation Agent
- **Purpose**: Bridge the gap between raw scores and human-readable actions.
- **Function**: Generates the final action (`ALLOW`, `CHALLENGE`, `BLOCK`) and the supporting rationale.

---

## 4. Governance & Policy Engine

The `PolicyEngine` acts as a final safety check. It enforces:
- **Action Limits**: Preventing automated mass-blocking.
- **Escalation Rules**: Forcing human review on high-value or high-risk transactions regardless of AI confidence.
- **Role Restrictions**: Ensuring only human reviewers can perform permanent account terminations.

---

## 5. Audit & Data Flow

Data flows through the system in a **unidirectional, immutable path**. The `DecisionContext` is a frozen dataclass, ensuring that once a decision is in progress, its state cannot be modified, only appended to the audit trail.

For details on the storage architecture, see [docs/DATA_AUDIT_LAYER.md](DATA_AUDIT_LAYER.md).
