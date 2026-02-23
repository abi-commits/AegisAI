# AegisAI Deployment Guide

This document provides instructions for deploying AegisAI to production using AWS ECS (Fargate), Terraform, and Docker.

---

## 1. Prerequisites

- **AWS CLI**: Configured with appropriate credentials.
- **Terraform**: Version 1.5.0 or higher.
- **Docker**: For building and pushing container images.
- **Python**: Version 3.11+ for local testing and scripting.

---

## 2. Infrastructure Overview

AegisAI's infrastructure is managed via Terraform and includes:

- **ECS Cluster**: Serverless Fargate cluster for running the API and agents.
- **S3 Buckets**: 
  - `audit-logs`: Immutable storage for decision receipts.
  - `model-registry`: Storage for trained model artifacts.
- **DynamoDB Table**: Fast metadata index for operational lookups.
- **IAM Roles**: Granular permissions for task execution and storage access.
- **Networking**: VPC with public/private subnets and security groups.

---

## 3. Initial Setup

### AWS Configuration

```bash
# Set your AWS profile
export AWS_PROFILE=your-profile
export AWS_REGION=ap-south-1
```

### Infrastructure Provisioning

1.  **Initialize Terraform**:
    ```bash
    cd infra
    terraform init
    ```

2.  **Review the Plan**:
    ```bash
    terraform plan -var-file="production.tfvars"
    ```

3.  **Apply Changes**:
    ```bash
    terraform apply -var-file="production.tfvars"
    ```

---

## 4. Container Deployment

### Build and Push to ECR

1.  **Login to ECR**:
    ```bash
    aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin your-account-id.dkr.ecr.ap-south-1.amazonaws.com
    ```

2.  **Build the Image**:
    ```bash
    docker build -t aegis-ai -f docker/Dockerfile .
    ```

3.  **Tag and Push**:
    ```bash
    docker tag aegis-ai:latest your-account-id.dkr.ecr.ap-south-1.amazonaws.com/aegis-ai:latest
    docker push your-account-id.dkr.ecr.ap-south-1.amazonaws.com/aegis-ai:latest
    ```

### Update ECS Service

```bash
aws ecs update-service --cluster aegis-ai-production --service aegis-ai-service --force-new-deployment
```

---

## 5. CI/CD Pipeline

AegisAI uses GitHub Actions for automated CI/CD.

- **CI**: Runs on every pull request. Performs linting (Black, Pylint), type checking (Mypy), and unit tests.
- **CD**: Runs on merge to `main`. Builds the Docker image, pushes to ECR, and triggers a rolling update on ECS.

Workflow file: `.github/workflows/ci-cd.yml`

---

## 6. Environment Variables

The following environment variables are passed to the ECS container:

| Variable | Description |
|----------|-------------|
| `AUDIT_STORAGE_TYPE` | Storage backend (e.g., `s3`) |
| `S3_AUDIT_BUCKET` | Name of the S3 audit bucket |
| `DYNAMODB_METADATA_TABLE` | Name of the DynamoDB table |
| `LOG_LEVEL` | Application logging level (`INFO`, `DEBUG`, etc.) |
| `ENVIRONMENT` | Deployment environment (`production`, `staging`) |

---

## 7. Scaling and Performance

- **Horizontal Scaling**: Adjusted via the `desired_count` variable in Terraform.
- **Vertical Scaling**: Managed through `task_cpu` and `task_memory` settings.
- **Monitoring**: Use CloudWatch Container Insights and Prometheus metrics to identify bottlenecks.

---

## 8. Rollback Strategy

To roll back a deployment:

1.  **Revert the Git Commit**: Push a revert to the `main` branch.
2.  **Manual ECS Rollback**: 
    ```bash
    aws ecs update-service --cluster aegis-ai-production --service aegis-ai-service --task-definition aegis-ai-task-vN
    ```
    (Replace `vN` with the previous stable version number).
