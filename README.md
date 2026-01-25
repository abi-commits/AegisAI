# AegisAI  
### Agentic Fraud & Trust Intelligence System

AegisAI is a production-oriented, agentic AI system designed to detect and manage account takeover (ATO) fraud while preserving transparency, human oversight, and auditability.

Unlike traditional fraud systems that rely on opaque risk scores, AegisAI models fraud detection as a governed decision-making process. Multiple autonomous agents collaborate to assess risk, measure uncertainty, generate explanations, and escalate decisions to humans when appropriate.

---

## Why AegisAI Exists

Modern fraud systems optimize for detection accuracy but often fail in real-world deployment due to:
- High false-positive rates that harm legitimate users
- Lack of explainability for decisions
- No explicit handling of uncertainty
- Weak human-in-the-loop integration
- Poor audit and governance support

AegisAI addresses these gaps by treating trust as a system-level property rather than a model metric.

---

## Core Principles

- **No single model has decision authority**
- **AI must know when it is uncertain**
- **Irreversible actions require human approval**
- **Every decision is explainable and auditable**
- **Policy constraints override model outputs**

---

## System Overview

AegisAI focuses on a single high-impact scenario:
**Account Takeover (ATO) detection in digital banking / fintech systems**

The system processes login events and routes them through a set of bounded agents:
- Detection Agent
- Behavioral Consistency Agent
- Network & Evidence Agent
- Confidence & Calibration Agent
- Explanation & Action Agent

Final decisions are either executed automatically (low risk) or escalated to human reviewers (high uncertainty).

---

## Decision Lifecycle

1. Login event is ingested
2. Independent agents analyze the event in parallel
3. Signals are aggregated without decision-making
4. Confidence agent determines AI authority
5. Action is executed or escalated
6. Full audit trace is recorded

---

## Governance & Safety

- Deterministic policy rules constrain AI authority
- Human overrides are final and logged
- Failure cases are explicitly documented
- Model and policy versions are tracked per decision

---

## Demo Scenario

The repository includes a complete walkthrough of a suspicious login attempt involving:
- New device
- New geography
- Partial behavioral mismatch
- Ambiguous network evidence

The system intentionally escalates to a human reviewer instead of making an automated decision.

---

## Known Limitations

- Synthetic data only (no real customer data)
- Simplified behavioral signals
- Lightweight graph modeling

These limitations are deliberate to keep the system auditable and reproducible.

---

## Future Work

- Streaming ingestion
- Richer behavioral biometrics
- Online policy learning
- Advanced graph reasoning

---
