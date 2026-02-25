# Scaling Strategy & Considerations — AegisAI

This document outlines how AegisAI handles growth in traffic, data volume, and agent complexity, along with the key considerations for maintaining performance at scale.

---

## 1. Compute Scaling: Horizontal & Parallel

### Horizontal Scaling (API & Agents)
AegisAI is designed to run in stateless containers on **AWS ECS (Fargate)**.
- **Scaling Trigger**: Target tracking policies on CPU and Memory usage.
- **Isolation**: Each container handles a subset of requests, ensuring that a single heavy session doesn't impact global availability.

### Parallel Agent Execution
The `AgentRouter` uses a shared `ThreadPoolExecutor` (and is `asyncio`-ready) to run independent agents in parallel.
- **Constant Latency**: Adding a new independent agent (e.g., a "Geographic Risk Agent") does not increase the end-to-end latency linearly.
- **Bottleneck Identification**: We monitor individual agent execution times to identify which models require optimization or more dedicated resources.

---

## 2. Data Scaling: Tiered Storage

### Audit Store (S3)
S3 is virtually infinitely scalable. We optimize it by:
- **Prefix Partitioning**: Organizing logs by `year/month/day/environment/` to prevent performance degradation when listing large numbers of objects.
- **Lifecycle Policies**: Moving older audit logs to **S3 Glacier** for cost-effective long-term retention.

### Metadata Index (DynamoDB)
DynamoDB handles high-concurrency lookups with predictable latency.
- **Adaptive Capacity**: Automatically handles "hot" partitions if a specific user or session generates massive amounts of activity.
- **TTL (Time to Live)**: Automatically cleaning up operational metadata after 90 days to keep the table size (and cost) manageable without impacting the immutable S3 audit trail.

---

## 3. Scaling Considerations & Bottlenecks

### The "Hot Key" Problem
In DynamoDB, a single user ID generating thousands of logins per second could lead to partition throttling.
- **Mitigation**: We use a composite key (`PK#USER#{user_id} + SK#TIMESTAMP`) to distribute writes across the partition.

### Agent Resource Contention
Agents share the same CPU/Memory in the container.
- **Consideration**: High-complexity agents (like GNNs) can starve simpler tabular models.
- **Future Strategy**: Moving high-compute agents to their own microservices (e.g., AWS Lambda or dedicated ECS services) and calling them via internal gRPC/HTTP.

### Network Latency
As the agent count grows, the overhead of gathering context and serializing outputs increases.
- **Consideration**: We prioritize local, high-speed feature extraction over external API calls within the critical path.

---

## 4. Future Scaling Roadmap

- **Streaming Ingestion**: Moving from synchronous API calls to a **Kafka/Kinesis**-based event-driven architecture for real-time processing.
- **Edge Inference**: Deploying lightweight versions of the Detection Agent to the edge (e.g., Lambda@Edge) to reject obvious fraud before it hits the core orchestration layer.
- **Global Secondary Indexes**: Adding more GSIs as the need for different query patterns (e.g., "all blocks in a specific region") arises.
