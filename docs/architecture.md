# AegisAI — System Architecture

This document describes the internal architecture and design rationale of AegisAI.

---

## Architectural Goal

To design a fraud detection system that:
- Separates prediction from decision-making
- Handles uncertainty explicitly
- Preserves human authority
- Supports audit, compliance, and post-mortem analysis

---

## High-Level Components

1. Event Ingestion Layer
2. Agent Reasoning Layer
3. Decision Orchestration Layer
4. Governance & Audit Layer
5. Human Review Interface (simulated)

---

## Agent Reasoning Layer

### Detection Agent
- Purpose: Identify anomalous login behavior
- Output: Risk signal score + factors
- Constraint: Cannot make decisions

### Behavioral Consistency Agent
- Purpose: Compare current behavior with historical user patterns
- Output: Behavioral match score
- Constraint: No network context

### Network & Evidence Agent
- Purpose: Surface relational risk via shared infrastructure
- Output: Network risk score + evidence links
- Constraint: Evidence only, no verdicts

### Confidence & Calibration Agent
- Purpose: Determine whether AI is allowed to decide
- Output: Confidence score + decision permission
- Constraint: Cannot generate actions or explanations

### Explanation & Action Agent
- Purpose: Select action and generate explanation
- Output: Action + human-readable explanation
- Constraint: Must obey confidence and policy rules

---

## Orchestration Flow

- Agents execute in parallel
- No agent sees another agent’s internal reasoning
- Outputs are aggregated deterministically
- Decision authority is gated by confidence and policy

This design prevents cascading bias and overconfidence.

---

## Policy Engine

Policies are deterministic, versioned rules that override model outputs when necessary.

Examples:
- AI cannot permanently block accounts
- Low confidence requires human escalation
- High disagreement triggers review

Policies are externalized and auditable.

---

## Audit & Lineage

Every decision records:
- Input event metadata
- Agent outputs
- Confidence scores
- Final action
- Human override (if any)
- Model + policy versions

No data is overwritten. History is immutable.

---

## Failure-Aware Design

The system explicitly anticipates:
- False positives from travel or device changes
- False negatives from low-and-slow attacks
- Systemic risks from shared infrastructure
- Bias introduced by human overrides

Failures are logged, not hidden.

---

## Design Philosophy

AegisAI is intentionally conservative.

The system prioritizes:
- Trust over automation
- Accountability over accuracy
- Governance over optimization

This architecture is designed to survive audits, not demos.
