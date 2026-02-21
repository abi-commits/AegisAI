# ============================================
# AegisAI — Root Outputs
# ============================================

# ----- Networking -----

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.ecs.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.ecs.public_subnet_ids
}

# ----- ECS -----

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = module.ecs.service_name
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.ecs.alb_dns_name
}

output "api_url" {
  description = "Base URL for the AegisAI API"
  value       = "http://${module.ecs.alb_dns_name}"
}

# ----- Storage -----

output "audit_bucket_name" {
  description = "S3 bucket for audit logs"
  value       = module.storage.audit_bucket_name
}

output "model_registry_bucket_name" {
  description = "S3 bucket for model artifacts"
  value       = module.storage.model_registry_bucket_name
}

output "audit_table_name" {
  description = "DynamoDB table for audit records"
  value       = module.storage.audit_table_name
}

# ----- IAM -----

output "task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = module.iam.task_execution_role_arn
}

output "task_role_arn" {
  description = "ARN of the ECS task role"
  value       = module.iam.task_role_arn
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions OIDC role for CI/CD"
  value       = module.iam.github_actions_role_arn
}
