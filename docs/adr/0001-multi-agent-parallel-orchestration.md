# ADR 0001: Multi-Agent Parallel Orchestration

* **Status**: Accepted
* **Date**: 2026-02-23
* **Deciders**: AegisAI Core Team

---

## 1. Context & Problem Statement

Account Takeover (ATO) fraud detection requires analyzing diverse signals (behavior, network, device, etc.). A monolithic model often lacks explainability and becomes a single point of failure for decision-making. We need a way to combine specialized signals while maintaining high performance and clear decision lineage.

## 2. Decision Drivers

* **Explainability**: Each risk factor must be clearly attributable.
* **Resilience**: A failure in one domain (e.g., GNN infrastructure) shouldn't disable the entire detection pipeline.
* **Latency**: Decision response time must remain within acceptable limits (< 500ms).
* **Governance**: AI decisions must be gated by confidence and policy.

## 3. Considered Options

* **Option A**: Monolithic Deep Learning Model (Ensemble).
* **Option B**: Sequential Pipeline of Modular Models.
* **Option C**: **Parallel Multi-Agent Orchestration with Asyncio.**

## 4. Decision Outcome

* **Chosen Option**: **Option C**
* **Rationale**: Parallel execution using Python's `asyncio` allows us to run specialized agents (Detection, Behavior, Network) simultaneously, minimizing the latency penalty of modularity. Each agent operates on its own domain, providing independent evidence that the orchestrator synthesizes.

## 5. Consequences

* **Positive**: 
    - Improved explainability through specialized agent outputs.
    - Horizontal scalability of agent logic.
    - Strong decoupling of domain-specific risk scoring.
* **Negative**: 
    - Increased complexity in orchestration and error handling.
    - Overhead of managing multiple models and their dependencies.
* **Risks**: 
    - Potential for cascading latency if one agent becomes a bottleneck (mitigated by timeouts).
