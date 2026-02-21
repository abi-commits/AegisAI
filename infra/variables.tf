# ============================================
# AegisAI — Root Variables
# ============================================

# ----- General -----

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment (production, staging, dev)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging", "dev"], var.environment)
    error_message = "Environment must be one of: production, staging, dev."
  }
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "aegis-ai"
}

variable "aws_account_id" {
  description = "AWS Account ID"
  type        = string
  default     = "253490748872"
}

# ----- GitHub (CI/CD OIDC) -----

variable "github_org" {
  description = "GitHub organization or username"
  type        = string
  default     = "abi-commits"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "AegisAI"
}

# ----- Networking -----

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to deploy across"
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

# ----- ECS -----

variable "container_port" {
  description = "Container port for the AegisAI API"
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "Fargate task CPU units (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate task memory in MiB"
  type        = number
  default     = 2048
}

variable "desired_count" {
  description = "Desired number of ECS task instances"
  type        = number
  default     = 1
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository"
  type        = string
  default     = "ageis-ai"
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
