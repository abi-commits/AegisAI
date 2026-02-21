# ============================================
# AegisAI — Storage Module
# ============================================
# Creates:
#   1. S3 bucket for audit logs (versioned, encrypted, lifecycle)
#   2. S3 bucket for model registry artifacts
#   3. DynamoDB table for audit records
# ============================================

# ============================================
# 1. Audit Logs S3 Bucket
# ============================================

resource "aws_s3_bucket" "audit" {
  bucket = "${var.project_name}-audit-logs-${var.environment}"

  tags = {
    Name    = "${var.project_name}-audit-logs"
    Purpose = "Immutable audit trail for all AegisAI decisions"
  }
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket = aws_s3_bucket.audit.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id

  rule {
    id     = "audit-log-lifecycle"
    status = "Enabled"

    transition {
      days          = var.audit_log_retention_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.audit_log_archive_days
      storage_class = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 730
    }
  }
}

# ============================================
# 2. Model Registry S3 Bucket
# ============================================

resource "aws_s3_bucket" "model_registry" {
  bucket = "${var.project_name}-model-registry-${var.environment}"

  tags = {
    Name    = "${var.project_name}-model-registry"
    Purpose = "Versioned model artifacts and metadata"
  }
}

resource "aws_s3_bucket_versioning" "model_registry" {
  bucket = aws_s3_bucket.model_registry.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "model_registry" {
  bucket = aws_s3_bucket.model_registry.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "model_registry" {
  bucket = aws_s3_bucket.model_registry.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ============================================
# 3. DynamoDB Audit Table
# ============================================
# Stores structured audit records for fast querying.
# Supports queries by decision_id and by user+timestamp.

resource "aws_dynamodb_table" "audit" {
  name         = "${var.project_name}-audit-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "decision_id"
  range_key    = "timestamp"

  attribute {
    name = "decision_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  # GSI: Query audit records by user_id + timestamp
  global_secondary_index {
    name            = "user-timestamp-index"
    hash_key        = "user_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name    = "${var.project_name}-audit-table"
    Purpose = "Structured audit records for decision lineage"
  }
}
