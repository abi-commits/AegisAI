# ============================================
# AegisAI — ECS Module Variables
# ============================================

# ----- General -----

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

# ----- Networking -----

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "availability_zones" {
  description = "Availability zones for subnets"
  type        = list(string)
}

# ----- Container -----

variable "container_port" {
  description = "Container port for the API"
  type        = number
}

variable "task_cpu" {
  description = "Fargate task CPU units"
  type        = number
}

variable "task_memory" {
  description = "Fargate task memory in MiB"
  type        = number
}

variable "desired_count" {
  description = "Desired number of ECS task instances"
  type        = number
}

variable "ecr_repository_url" {
  description = "Full ECR repository URL (without tag)"
  type        = string
}

# ----- IAM -----

variable "task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  type        = string
}

variable "task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

# ----- Storage references -----

variable "audit_bucket_name" {
  description = "Name of the audit S3 bucket"
  type        = string
}

variable "audit_table_name" {
  description = "Name of the audit DynamoDB table"
  type        = string
}

variable "model_registry_bucket_name" {
  description = "Name of the model registry S3 bucket"
  type        = string
}

# ----- Application -----

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "enable_api_docs" {
  description = "Enable FastAPI /docs endpoint"
  type        = bool
  default     = false
}

variable "health_check_path" {
  description = "Health check endpoint path"
  type        = string
  default     = "/ready"
}

variable "health_check_interval" {
  description = "Health check interval in seconds"
  type        = number
  default     = 30
}

variable "deregistration_delay" {
  description = "ALB target group deregistration delay in seconds"
  type        = number
  default     = 60
}
