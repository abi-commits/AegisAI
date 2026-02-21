# ============================================
# AegisAI — IAM Module Variables
# ============================================

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "aws_account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "github_org" {
  description = "GitHub organization or username for OIDC"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name for OIDC"
  type        = string
}

variable "audit_bucket_arn" {
  description = "ARN of the audit S3 bucket"
  type        = string
}

variable "model_registry_bucket_arn" {
  description = "ARN of the model registry S3 bucket"
  type        = string
}

variable "audit_table_arn" {
  description = "ARN of the audit DynamoDB table"
  type        = string
}
