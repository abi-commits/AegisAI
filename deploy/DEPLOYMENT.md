# AegisAI Production Deployment Guide

## Overview

AegisAI deploys to AWS ECS (Fargate) via GitHub Actions with OIDC authentication. No long-lived AWS credentials are stored in the repository.

---

## Prerequisites

- AWS Account with ap-south-1 region configured
- ECS cluster: `aegis-ai-cluster` (created)
- ECR repository: `ageis-ai` (created)
- IAM OIDC provider: `token.actions.githubusercontent.com` (created)
- GitHub repository with write access to Secrets

---

## 1. IAM Setup (One-time)

### Create GitHub Actions OIDC Role

```bash
# Set variables
export AWS_ACCOUNT_ID=253490748872
export ROLE_NAME=GitHubActionsDeployRole
export TRUST_FILE=deploy/oidc-trust.json
export POLICY_FILE=deploy/github-actions-policy.json

# Create role
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file://$TRUST_FILE

# Attach permissions policy
aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name GitHubActionsDeployPolicy \
  --policy-document file://$POLICY_FILE

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
echo "Role ARN: $ROLE_ARN"
```

### Add GitHub Secret

In your GitHub repo:
1. Settings → Secrets and variables → Actions
2. New repository secret:
   - Name: `GHA_OIDC_ROLE_ARN`
   - Value: `arn:aws:iam::253490748872:role/GitHubActionsDeployRole`

---

## 2. ECS Task Setup

### Create task execution role (if not already created)

```bash
# Trust policy for ECS
cat > /tmp/ecs-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document file:///tmp/ecs-trust.json

# Attach managed policy
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

### Create ECS service (if needed)

```bash
# Get your VPC/subnet/SG details
export SUBNETS=subnet-xxxxx,subnet-yyyyy
export SECURITY_GROUP=sg-xxxxx

aws ecs create-service \
  --cluster aegis-ai-cluster \
  --service-name aegis-ai \
  --task-definition aegis-ai \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
  --region ap-south-1
```

---

## 3. Deployment Flow

### Push to Production

```bash
git push origin production
```

This triggers `.github/workflows/ci-cd.yml`:
1. **Test** job runs unit tests
2. **Deploy** job (if test passes):
   - Assumes OIDC role (no credentials needed)
   - Logs into ECR
   - Builds and pushes Docker image with commit SHA tag
   - Registers new ECS task definition
   - Updates ECS service and waits for stability

---

## 4. Verify Deployment

```bash
# Check service status
aws ecs describe-services \
  --cluster aegis-ai-cluster \
  --services aegis-ai \
  --region ap-south-1

# Check task status
aws ecs list-tasks \
  --cluster aegis-ai-cluster \
  --service-name aegis-ai \
  --region ap-south-1

# Get task logs
aws ecs describe-tasks \
  --cluster aegis-ai-cluster \
  --tasks <task-arn> \
  --region ap-south-1 | jq '.tasks[0].containerInstanceArn'

# View CloudWatch logs (if configured)
aws logs tail /ecs/aegis-ai --follow --region ap-south-1
```

---

## 5. Secrets Management

### Do NOT store credentials in environment files

For sensitive config (API keys, DB passwords):

1. **Option A: AWS Secrets Manager** (recommended)
   ```bash
   aws secretsmanager create-secret --name aegis-api-key --secret-string "xxx"
   ```
   Then reference in task definition with `secrets` block.

2. **Option B: Parameter Store**
   ```bash
   aws ssm put-parameter --name /aegis/api-key --value "xxx" --type SecureString
   ```

3. **Option C: Docker image env vars** (only for non-sensitive settings)
   Update `.github/workflows/ci-cd.yml` deploy job environment block.

---

## 6. Rollback

If deployment fails or you need to roll back:

```bash
# Update service to previous task definition
aws ecs update-service \
  --cluster aegis-ai-cluster \
  --service aegis-ai \
  --task-definition aegis-ai:N \
  --region ap-south-1
```

where `N` is the previous revision number.

---

## 7. Monitoring & Alerts

### CloudWatch

Set up alarms for:
- ECS task CPU/memory
- API error rates (4xx, 5xx)
- Audit log write failures

### Example alarm

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name aegis-api-high-errors \
  --alarm-description "Alert if 5xx errors exceed 5%" \
  --metric-name 5XXError \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

---

## 8. Production Checklist

- [ ] OIDC role created and GitHub secret set
- [ ] ECS cluster and service configured
- [ ] Task execution role has CloudWatch Logs permission
- [ ] S3 audit bucket exists with versioning enabled
- [ ] Credentials removed from all `.env` files
- [ ] `.gitignore` includes `*.env*`
- [ ] CI/CD pipeline tested on `production` branch
- [ ] CloudWatch alarms configured
- [ ] Backup/DR plan documented

---

## Support

For issues, check:
- GitHub Actions logs (Workflows tab)
- ECS task logs (CloudWatch or `aws ecs describe-tasks`)
- ECR repository for image push failures
- IAM permissions on the OIDC role
