# ============================================
# AegisAI — Terraform Providers & Backend
# ============================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state in S3 with DynamoDB locking
  # Create these resources manually before first `terraform init`:
  #   aws s3api create-bucket --bucket aegis-ai-terraform-state --region ap-south-1 \
  #     --create-bucket-configuration LocationConstraint=ap-south-1
  #   aws s3api put-bucket-versioning --bucket aegis-ai-terraform-state \
  #     --versioning-configuration Status=Enabled
  #   aws dynamodb create-table --table-name aegis-ai-terraform-lock \
  #     --attribute-definitions AttributeName=LockID,AttributeType=S \
  #     --key-schema AttributeName=LockID,KeyType=HASH \
  #     --billing-mode PAY_PER_REQUEST --region ap-south-1
  backend "s3" {
    bucket         = "aegis-ai-terraform-state"
    key            = "infra/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "aegis-ai-terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "AegisAI"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
