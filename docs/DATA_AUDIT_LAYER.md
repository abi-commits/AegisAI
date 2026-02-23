# Governance & Audit Layer — AegisAI

This document provides a deep dive into the **Governance & Safety** and **Scaling Strategy** of AegisAI’s data persistence layer. It details how the system ensures decision immutability, regulatory compliance, and high-performance lookups.

---

## 1. Architectural Strategy: The Dual-Backend Approach

To satisfy both regulatory requirements (immutability) and operational requirements (latency), AegisAI employs a tiered storage strategy:

1.  **Immutable Audit Store (S3)**: The "Source of Truth." Uses a Write-Once-Read-Many (WORM) pattern for long-term, tamper-proof audit trails.
2.  **Operational Metadata Index (DynamoDB)**: The "Fast Path." A denormalized index optimized for single-digit millisecond lookups of decision state and human overrides.

---

## 2. Governance & Safety: Ensuring Immutability

### Hash-Chain Integrity
Every audit entry is cryptographically linked to its predecessor. This "hash chain" ensures that:
-   **No Deletions**: Removing an entry breaks the chain.
-   **No Modifications**: Altering an entry changes its hash and invalidates the subsequent entries.
-   **Traceability**: Each decision has a verified lineage back to the system initialization.

### Object Lock & Versioning (S3)
For production environments, we enable **S3 Object Lock** in "Compliance Mode."
-   **WORM Protection**: Prevents any user (including root) from deleting or overwriting logs for a defined retention period.
-   **Versioning**: All versions of an object are retained, providing a complete history of any (theoretical) attempts to modify data.

---

## 3. Scaling Strategy: Performance at Scale

### Denormalized Data Access (DynamoDB)
The metadata layer is designed around **Single-Table Design** principles to avoid joins and ensure predictable performance regardless of scale:

-   **PK**: `PK#{ENTITY_TYPE}#{PRIMARY_ID}` (e.g., `PK#DECISION#dec_123`)
-   **SK**: `SK#{ENTITY_TYPE}#{TIMESTAMP}`
-   **GSI1 (User View)**: Allows sub-10ms retrieval of all decisions for a specific user ID.
-   **GSI2 (Session View)**: Correlates multiple decisions within a single user session.

### Partitioning & Throughput
-   **S3 Partitioning**: Logs are partitioned by `year/month/day/environment`, enabling efficient "Audit Discovery" jobs that only scan relevant time ranges.
-   **Auto-Scaling**: Both S3 and DynamoDB are serverless and auto-scale to handle bursts in login volume without manual intervention.

---

## 4. Compliance & Regulatory Alignment

AegisAI’s audit layer is built to satisfy the requirements of:
-   **GDPR/CCPA**: Audit trails for data processing and consent.
-   **PCI-DSS**: Immutable transaction and access logs.
-   **SOC 2**: Comprehensive evidence for security and availability controls.

| Requirement | Implementation | Proves |
|-------------|----------------|--------|
| **Immutability** | S3 Object Lock | Data has not been deleted. |
| **Integrity** | Hash Chaining | Data has not been altered. |
| **Availability** | Multi-AZ S3/Dynamo | Data is always accessible. |
| **Auditability** | GSI Lookups | Decisions are searchable. |

---

## 5. Failure Modes & Recovery

-   **Audit Failure**: If the audit write fails, the system triggers a **"Fail-Safe" Escalation**. No decision is returned to the client until it is successfully persisted to the audit trail.
-   **Index Desync**: If DynamoDB is out of sync with S3, a **Recovery Job** re-scans the S3 JSONL logs to rebuild the metadata index.

---

## 6. Implementation Reference

The unified audit trail is managed through the `UnifiedAuditTrail` class in `src/aegis_ai/governance/audit/`.

```python
# Example: Persisting a governed decision
audit_trail.log_decision(
    decision_id="dec_abc123",
    action="CHALLENGE",
    confidence_score=0.92,
    policy_version="1.0.4",
    metadata={"agent_disagreement": 0.12}
)
```

For detailed API usage and environment configuration, refer to the [source code](../../src/aegis_ai/governance/audit/unified_trail.py).
