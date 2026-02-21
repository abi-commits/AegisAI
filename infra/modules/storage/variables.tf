# ============================================
# AegisAI — Storage Module Variables
# ============================================

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "audit_log_retention_days" {
  description = "Days to retain audit logs before transitioning to IA storage"
  type        = number
  default     = 90
}

variable "audit_log_archive_days" {
  description = "Days before transitioning audit logs to Glacier"
  type        = number
  default     = 365
}
