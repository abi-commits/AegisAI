# ============================================
# AegisAI — Storage Module Outputs
# ============================================

# ----- Audit Bucket -----

output "audit_bucket_name" {
  description = "Name of the audit logs S3 bucket"
  value       = aws_s3_bucket.audit.id
}

output "audit_bucket_arn" {
  description = "ARN of the audit logs S3 bucket"
  value       = aws_s3_bucket.audit.arn
}

# ----- Model Registry Bucket -----

output "model_registry_bucket_name" {
  description = "Name of the model registry S3 bucket"
  value       = aws_s3_bucket.model_registry.id
}

output "model_registry_bucket_arn" {
  description = "ARN of the model registry S3 bucket"
  value       = aws_s3_bucket.model_registry.arn
}

# ----- Audit DynamoDB Table -----

output "audit_table_name" {
  description = "Name of the audit DynamoDB table"
  value       = aws_dynamodb_table.audit.name
}

output "audit_table_arn" {
  description = "ARN of the audit DynamoDB table"
  value       = aws_dynamodb_table.audit.arn
}
