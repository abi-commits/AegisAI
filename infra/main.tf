# ============================================
# AegisAI — Root Module
# ============================================
#
# Composes IAM, Storage, and ECS modules into a
# complete infrastructure for the AegisAI fraud
# detection system running on AWS ECS Fargate.
# ============================================

# ----- Storage (S3 + DynamoDB) -----

module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
}

# ----- IAM Roles & Policies -----

module "iam" {
  source = "./modules/iam"

  project_name   = var.project_name
  environment    = var.environment
  aws_region     = var.aws_region
  aws_account_id = var.aws_account_id
  github_org     = var.github_org
  github_repo    = var.github_repo

  # Storage ARNs for task role policies
  audit_bucket_arn          = module.storage.audit_bucket_arn
  model_registry_bucket_arn = module.storage.model_registry_bucket_arn
  audit_table_arn           = module.storage.audit_table_arn
}

# ----- ECS (Networking + Cluster + Service) -----

module "ecs" {
  source = "./modules/ecs"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones

  # Container config
  container_port = var.container_port
  task_cpu       = var.task_cpu
  task_memory    = var.task_memory
  desired_count  = var.desired_count

  # ECR image
  ecr_repository_url = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}"

  # IAM roles
  task_execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn           = module.iam.task_role_arn

  # Storage references (passed as env vars to the container)
  audit_bucket_name          = module.storage.audit_bucket_name
  audit_table_name           = module.storage.audit_table_name
  model_registry_bucket_name = module.storage.model_registry_bucket_name

  # Application config
  log_level       = var.log_level
  enable_api_docs = var.enable_api_docs
}
