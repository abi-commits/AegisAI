# 4️⃣ Data & Audit Layer — Receipts Live Forever

## Overview

The AegisAI audit layer provides an immutable, regulator-friendly audit trail with two complementary storage backends:

1. **S3 Audit Store**: Append-only JSONL logs (immutable receipts)
2. **DynamoDB Metadata Store**: Fast operational lookups (no joins, no drama)

This architecture ensures:
- ✅ **Immutability**: Append-only logs, versioning, optional Object Lock
- ✅ **Performance**: Single-digit millisecond lookups via DynamoDB
- ✅ **Compliance**: Date/environment partitioning, automatic TTL cleanup
- ✅ **Integrity**: Hash chain verification, tamper detection
- ✅ **Scalability**: Serverless, auto-scaling, pay-per-request

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Unified Audit Trail                        │
│         (UnifiedAuditTrail - Single Entry Point)             │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
        ┌───────▼────────┐     ┌───────▼──────────┐
        │  S3 Logs       │     │ DynamoDB Index   │
        │  (Immutable)   │     │ (Fast Lookups)   │
        └────────────────┘     └──────────────────┘
```

### S3 Audit Store (Write-Once, Read-Many)

**Purpose**: Immutable audit trail for regulatory compliance

**Features**:
- ✅ Append-only JSONL logs
- ✅ Object versioning (all versions retained)
- ✅ Object Lock (governance/compliance mode)
- ✅ Date/environment partitioning
- ✅ Hash chain integrity verification
- ✅ Automatic backups

**Storage Path Format**:
```
s3://aegis-audit-logs/audit-logs/{ENVIRONMENT}/{DATE}/audit.jsonl

Example:
s3://aegis-audit-logs/audit-logs/production/2026-01-29/audit.jsonl
```

**Data Format**: JSONL (JSON Lines)
```jsonl
{"event_type":"decision","decision_id":"dec_abc123","session_id":"ses_def456","user_id":"usr_ghi789","action":"ALLOW","confidence_score":0.95,"decided_by":"AI","policy_version":"1.0","timestamp":"2026-01-29T10:30:00.000Z","entry_hash":"sha256_hash","previous_hash":"sha256_prev"}
{"event_type":"escalation","decision_id":"dec_abc123","escalation_type":"POLICY","reason":"Risk threshold exceeded","status":"PENDING","timestamp":"2026-01-29T10:31:00.000Z","entry_hash":"sha256_hash2","previous_hash":"sha256_hash"}
```

**Benefits**:
- Immutable (can't be deleted or modified, only appended)
- Versioning provides point-in-time recovery
- Object Lock provides regulatory compliance
- Hash chain provides tamper detection proof
- Natural partitioning by date and environment
- Write-once, read-many (WORM) pattern

### DynamoDB Operational Metadata (Fast Lookups)

**Purpose**: Quick lookups without joins, denormalized data

**Features**:
- ✅ Single-digit millisecond queries
- ✅ No joins required (all data denormalized)
- ✅ Global Secondary Indexes for flexible queries
- ✅ TTL for automatic cleanup of old records
- ✅ Pay-per-request billing

**Table Schema**:

```
Primary Key:
  pk (HASH): PK#{ENTITY_TYPE}#{PRIMARY_ID}
             Example: PK#DECISION#dec_abc123
  sk (RANGE): SK#{ENTITY_TYPE}#{TIMESTAMP}
              Example: SK#DECISION#2026-01-29T10:30:00Z

Global Secondary Index 1 (gsi1_pk-gsi1_sk-index):
  For user/entity-type queries
  gsi1_pk: {ENTITY_TYPE}#{SECONDARY_ID}
           Example: DECISION#usr_ghi789
  gsi1_sk: TIMESTAMP

Global Secondary Index 2 (gsi2_pk-gsi2_sk-index):
  For decision/session queries
  gsi2_pk: {ENTITY_TYPE}#{CORRELATION_ID}
           Example: SESSION#ses_def456 or DECISION#dec_abc123
  gsi2_sk: TIMESTAMP

TTL:
  ttl_timestamp: Unix timestamp for auto-cleanup (default: 90 days)
```

**Entities**:

1. **Decision Index**
   - `decision_id`, `session_id`, `user_id` for fast lookups
   - Queryable by: decision_id, user_id, session_id
   - Example: "Show me all decisions for user_ghi789"

2. **Escalation Tracking**
   - `decision_id`, `escalation_type`, `status`
   - Queryable by: decision_id, escalation_type
   - Example: "Show me all pending escalations for this decision"

3. **Human Override References**
   - `override_id`, `original_decision_id`, `reviewer_id`
   - Queryable by: decision_id, reviewer_id
   - Example: "Show me all overrides made by analyst_xyz"

**Benefits**:
- ✅ Single-digit millisecond response times
- ✅ No complex joins required
- ✅ Denormalized schema optimized for queries
- ✅ Auto-scaling with serverless DynamoDB
- ✅ TTL for automatic cleanup

## Usage

### 1. Basic Decision Logging

```python
from src.aegis_ai.governance.audit.unified_trail import UnifiedAuditTrail

# Create unified audit trail (S3 + DynamoDB)
audit_trail = UnifiedAuditTrail(use_dynamodb=True)

# Log a decision (writes to both S3 and DynamoDB)
entry = audit_trail.log_decision(
    decision_id="dec_abc123",
    session_id="ses_def456",
    user_id="usr_ghi789",
    action="ALLOW",
    confidence_score=0.95,
    decided_by="AI",
    policy_version="1.0",
    metadata={"risk_score": 0.2, "model_version": "v2.1"},
)

print(f"Decision logged: {entry.decision_id}")
```

### 2. Fast Lookups via DynamoDB

```python
# Get decision by ID (single-digit milliseconds)
decision = audit_trail.get_decision_by_id("dec_abc123")
print(f"Action: {decision['action']}, Confidence: {decision['confidence_score']}")

# Get all decisions for a user (fast GSI query)
user_decisions = audit_trail.get_user_decisions("usr_ghi789", limit=100)
print(f"User made {len(user_decisions)} decisions")

# Get all decisions in a session (fast GSI query)
session_decisions = audit_trail.get_session_decisions("ses_def456")
print(f"Session had {len(session_decisions)} decisions")
```

### 3. Escalation Tracking

```python
# Create an escalation
escalation_id, entry = audit_trail.log_escalation(
    decision_id="dec_abc123",
    escalation_type="POLICY",
    reason="Risk threshold exceeded",
    escalated_to="risk_team",
    session_id="ses_def456",
    user_id="usr_ghi789",
)

print(f"Escalation created: {escalation_id}")

# Later: update escalation status
audit_trail.update_escalation_status(
    escalation_id=escalation_id,
    status="RESOLVED",
    resolution="Approved by analyst",
    resolved_by="analyst_xyz",
)
```

### 4. Human Override Recording

```python
# Record a human override
override_entry = audit_trail.log_human_override(
    override_id="ovr_123",
    original_decision_id="dec_abc123",
    original_action="BLOCK",
    original_confidence=0.85,
    new_action="ALLOW",
    override_type="APPROVE",
    reason="False positive - customer confirmed legitimate",
    reviewer_id="analyst_xyz",
    reviewer_role="fraud_analyst",
    session_id="ses_def456",
    user_id="usr_ghi789",
    metadata={"notes": "Called customer, confirmed identity"},
)

# Later: get the override for a decision
override = audit_trail.get_override_for_decision("dec_abc123")
if override:
    print(f"Decision was overridden by {override['reviewer_id']}: {override['reason']}")

# Or get all overrides by a reviewer
reviewer_overrides = audit_trail.get_reviewer_overrides("analyst_xyz", limit=50)
print(f"Analyst made {len(reviewer_overrides)} overrides")
```

## Environment Configuration

### Setup S3 Bucket

```bash
# Create S3 bucket
aws s3api create-bucket \
  --bucket aegis-audit-logs \
  --region us-east-1

# Enable versioning (automatic point-in-time recovery)
aws s3api put-bucket-versioning \
  --bucket aegis-audit-logs \
  --versioning-configuration Status=Enabled

# (Optional) Enable Object Lock for regulatory compliance
# NOTE: Can only be enabled at bucket creation time
aws s3api create-bucket \
  --bucket aegis-audit-logs-locked \
  --region us-east-1 \
  --object-lock-enabled-for-bucket
```

### Setup DynamoDB Table

```bash
# Create DynamoDB table with GSIs
aws dynamodb create-table \
  --table-name aegis-operational-metadata \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
    AttributeName=gsi1_pk,AttributeType=S \
    AttributeName=gsi1_sk,AttributeType=S \
    AttributeName=gsi2_pk,AttributeType=S \
    AttributeName=gsi2_sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --global-secondary-indexes \
    IndexName=gsi1_pk-gsi1_sk-index,\
Keys=[{AttributeName=gsi1_pk,KeyType=HASH},{AttributeName=gsi1_sk,KeyType=RANGE}],\
Projection={ProjectionType=ALL},\
    IndexName=gsi2_pk-gsi2_sk-index,\
Keys=[{AttributeName=gsi2_pk,KeyType=HASH},{AttributeName=gsi2_sk,KeyType=RANGE}],\
Projection={ProjectionType=ALL} \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Enable TTL for automatic cleanup (90-day retention)
aws dynamodb update-time-to-live \
  --table-name aegis-operational-metadata \
  --time-to-live-specification AttributeName=ttl_timestamp,Enabled=true \
  --region us-east-1
```

### Environment Variables

```bash
# .env or .env.audit
export AUDIT_STORAGE_TYPE=s3          # S3 backend (recommended)
export S3_AUDIT_BUCKET=aegis-audit-logs
export S3_AUDIT_PREFIX=audit-logs/
export S3_ENVIRONMENT=production       # or: development, staging
export S3_ENABLE_VERSIONING=true
export S3_ENABLE_OBJECT_LOCK=false    # Set to true for locked compliance
export DYNAMODB_METADATA_TABLE=aegis-operational-metadata
export AWS_REGION=us-east-1
export ENABLE_HASH_CHAIN=true          # Enable tamper detection
```

## Integrity Verification

### Hash Chain Verification

Each entry includes a hash of the previous entry, creating a cryptographic chain:

```python
# Verify integrity of audit logs
is_valid = audit_trail.audit_logger.verify_integrity(date="2026-01-29")
if is_valid:
    print("✅ Audit log integrity verified - no tampering detected")
else:
    print("❌ Audit log integrity check failed - potential tampering!")
```

### What Hash Chain Proves

- ✅ No entries were deleted (would break the chain)
- ✅ No entries were modified (would change the hash)
- ✅ No entries were reordered (timestamps would be inconsistent)
- ✅ Chronological ordering is preserved

## Performance Characteristics

### S3 Audit Store

| Operation | Latency | Notes |
|-----------|---------|-------|
| Append Entry | 100-300ms | Network round-trip to S3 |
| List/Filter | 200-500ms | Depends on log size |
| Verify Integrity | 500ms-2s | Full chain verification |

### DynamoDB Metadata Store

| Operation | Latency | Notes |
|-----------|---------|-------|
| Get Decision | 1-5ms | Direct lookup |
| Query by User | 5-10ms | GSI query |
| Query by Session | 5-10ms | GSI query |
| Update Status | 5-10ms | Conditional update |

## Cost Optimization

### S3

- **Pricing**: $0.023 per GB/month for storage
- **Versioning**: Stores all versions (+storage cost)
- **Transfer**: Minimal (mostly internal AWS)
- **Estimate**: ~$0.50-2.00/month for typical deployment

### DynamoDB

- **Pricing**: On-demand (pay per request)
- **Read**: $0.25 per 1M read units
- **Write**: $1.25 per 1M write units
- **TTL**: Free (automatic cleanup)
- **Estimate**: ~$10-50/month for typical deployment

### Total

**Typical Monthly Cost**: $20-60 for full audit trail with S3 + DynamoDB

Compare to:
- Manual data store: $500-2000+/month
- Managed audit service: $200-1000+/month

## Compliance Features

### Audit Log Requirements Met

| Requirement | S3 | DynamoDB | Notes |
|------------|----|-----------:|-------|
| Immutable logs | ✅ | N/A | Append-only WORM |
| Tamper detection | ✅ | - | Hash chain verification |
| Versioning | ✅ | N/A | Object versioning |
| Object Lock | ✅* | N/A | Governance mode |
| Retention policy | ✅ | ✅ | TTL auto-cleanup |
| Access logging | ✅ | ✅ | S3 access logs, CloudTrail |
| Encryption | ✅ | ✅ | S3 SSE-S3, DynamoDB encryption at rest |

*Optional, requires bucket-level configuration

### Regulatory Compliance

- ✅ **GDPR**: Audit trails for consent/processing records
- ✅ **PCI-DSS**: Immutable transaction logs
- ✅ **SOC 2**: Comprehensive audit trail with hash verification
- ✅ **HIPAA**: Immutable PHI access logs
- ✅ **Financial**: All decisions permanently recorded

## Monitoring & Alerting

### CloudWatch Metrics

```python
import boto3

cloudwatch = boto3.client("cloudwatch")

# Monitor S3 append latency
cloudwatch.get_metric_statistics(
    Namespace="AWS/S3",
    MetricName="PutObject",
    Dimensions=[{"Name": "BucketName", "Value": "aegis-audit-logs"}],
    StartTime=datetime.now() - timedelta(hours=1),
    EndTime=datetime.now(),
    Period=300,
    Statistics=["Average", "Maximum"],
)

# Monitor DynamoDB latency
cloudwatch.get_metric_statistics(
    Namespace="AWS/DynamoDB",
    MetricName="ConsumedWriteCapacityUnits",
    Dimensions=[{"Name": "TableName", "Value": "aegis-operational-metadata"}],
    StartTime=datetime.now() - timedelta(hours=1),
    EndTime=datetime.now(),
    Period=60,
    Statistics=["Sum"],
)
```

## Troubleshooting

### S3 Issues

**Problem**: `NoSuchKey` error when reading logs
```python
# Verify bucket and prefix
audit_trail.audit_logger._store.bucket_name  # Check bucket name
audit_trail.audit_logger._store.prefix       # Check prefix
audit_trail.audit_logger._store.environment  # Check environment
```

**Problem**: Object Lock violation
```bash
# Check Object Lock status
aws s3api get-object-lock-configuration --bucket aegis-audit-logs

# If locked, use COMPLIANCE mode for regulatory requirements
aws s3api put-object-lock-configuration \
  --bucket aegis-audit-logs \
  --object-lock-configuration='{"ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"COMPLIANCE","Days":90}}}'
```

### DynamoDB Issues

**Problem**: Slow queries
```python
# Check table status
audit_trail.dynamodb_metadata.table.table_status

# Monitor consumed units
response = audit_trail.dynamodb_metadata.table.get_item(...)
print(f"Consumed units: {response['ResponseMetadata']['HTTPHeaders']['x-amzn-dynamodb-consumed-capacity']}")
```

**Problem**: TTL not cleaning up
```bash
# Verify TTL is enabled
aws dynamodb describe-time-to-live --table-name aegis-operational-metadata

# Check oldest items
aws dynamodb scan --table-name aegis-operational-metadata --limit 1
```

## Related Architecture

- **Governance Layer**: Uses audit trail for override/escalation tracking
- **API Gateway**: Logs decisions through audit trail
- **Agent Router**: Logs agent outputs and decisions
- **Policy Engine**: Logs policy checks and violations

## Files

- [s3_store.py](../s3_store.py) - S3 audit store implementation
- [dynamodb_metadata.py](../dynamodb_metadata.py) - DynamoDB metadata store
- [unified_trail.py](../unified_trail.py) - Unified audit trail API
- [config.py](../config.py) - Configuration and factory methods
- [test_s3_audit_store.py](../../../tests/unit/governance/test_s3_audit_store.py) - S3 tests
- [test_dynamodb_metadata.py](../../../tests/unit/governance/test_dynamodb_metadata.py) - DynamoDB tests
- [test_unified_audit_trail.py](../../../tests/unit/governance/test_unified_audit_trail.py) - Integration tests

## Key Insights

> **Receipts Live Forever**: S3 append-only logs provide an immutable audit trail that regulators love. You can't delete or modify entries, only read them.

> **No Joins, No Drama**: DynamoDB denormalized schema means fast lookups without complex queries. Query response time is consistent and predictable.

> **Hash Chain = Proof**: The cryptographic hash chain proves no entries were deleted, modified, or reordered. It's mathematically verifiable tamper evidence.

> **Serverless = Scalable**: Auto-scaling S3 and DynamoDB mean no capacity planning, no infrastructure management. Pay only for what you use.
