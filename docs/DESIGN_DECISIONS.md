# Design Decisions & Tradeoffs — AegisAI

This document outlines the rationale behind the technical choices and the compromises made during the development of AegisAI.

---

## 1. Modular Agent vs. Monolithic Model

**Decision**: A multi-agent approach where each agent has a specific scope.

**Rationale**: 
- **Explainability**: Each agent provides a clear signal, making it easier to understand *why* the system reached a certain risk score.
- **Resilience**: If one model fails or needs retraining, the entire system doesn't collapse.
- **Specialization**: We can use the best tool for the job (e.g., GNN for network risk, XGBoost for tabular data).

**Tradeoff**: 
- **Increased Latency**: Running multiple models in parallel adds overhead.
- **Complexity**: Managing agent communication and orchestration is more difficult.

---

## 2. Frozen Dataclasses for Decision Context

**Decision**: Using `@dataclass(frozen=True)` for the `DecisionContext`.

**Rationale**: 
- **Audit Integrity**: Ensures that once a decision cycle starts, its input and intermediate states cannot be modified by any agent or process.
- **Immutability**: Simplifies state management in an asynchronous, multi-agent environment.

**Tradeoff**: 
- **Memory Overhead**: Creating new copies of the context for each state transition.

---

## 3. S3 & DynamoDB for Audit Storage

**Decision**: Using S3 for JSONL logs and DynamoDB for a metadata index.

**Rationale**: 
- **S3 (WORM)**: Perfect for immutable, long-term storage required by regulators.
- **DynamoDB**: Provides fast, single-digit millisecond lookups for operational needs (e.g., "What was the decision for session X?").

**Tradeoff**: 
- **Consistency**: Maintaining synchronization between S3 and DynamoDB requires a "Unified Audit Trail" wrapper.

---

## 4. Policy Engine over Machine Learning for Final Action

**Decision**: Using a deterministic `PolicyEngine` to enforce final actions.

**Rationale**: 
- **Safety**: Prevents a model from making catastrophic errors (e.g., mass-blocking users) that violate business rules.
- **Transparency**: Policy rules are human-readable and easily auditable by compliance teams.

**Tradeoff**: 
- **Rigidity**: Hard-coded rules might be too slow to adapt to new fraud patterns without manual updates.

---

## 5. AsyncIO for Parallel Agent Execution

**Decision**: Utilizing Python's `asyncio` for the `AgentRouter`.

**Rationale**: 
- **Performance**: Minimizes the impact of the multi-agent overhead by running network-bound or model-inference tasks in parallel.
- **Scalability**: Can handle higher throughput than a synchronous sequential execution.

**Tradeoff**: 
- **Debugging Difficulty**: Asynchronous code is notoriously harder to debug and trace compared to synchronous code.
- **Library Support**: Requires all components in the chain to be async-friendly to get the full benefit.
