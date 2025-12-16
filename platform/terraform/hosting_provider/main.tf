terraform {
  # Remote backend configuration
  # <TF_HOSTING_REMOTE_BACKEND>
}

locals {
  cluster_name         = "<PRIMARY_CLUSTER_NAME>"
  cluster_version      = "<CLUSTER_VERSION>"
  cluster_network_cidr = "<CLUSTER_NETWORK_CIDR>"
  region               = "<CLOUD_REGION>"
  email                = ["<OWNER_EMAIL>"]
  domain_name          = "<DOMAIN_NAME>"
  
  # Existing VPC configuration (optional)
  # If vpc_id is empty, a new VPC will be created
  vpc_id               = "<VPC_ID>"
  private_subnet_ids   = <PRIVATE_SUBNET_IDS>
  public_subnet_ids    = <PUBLIC_SUBNET_IDS>
  intra_subnet_ids     = <INTRA_SUBNET_IDS>
  database_subnets     = <DATABASE_SUBNET_IDS>
  
  # ACM certificate for ALB Ingress Controller / Gateway API
  acm_certificate_arn  = "<ACM_CERTIFICATE_ARN>"
  
  # Security groups (optional)
  cluster_security_group_id             = "<CLUSTER_SECURITY_GROUP_ID>"
  additional_cluster_security_group_ids = <ADDITIONAL_CLUSTER_SECURITY_GROUP_IDS>
  
  # CloudWatch configuration
  cloudwatch_log_group_retention_in_days = <CLOUDWATCH_LOG_RETENTION_DAYS>
  
  # Node security group additional rules
  node_security_group_additional_rules = <NODE_SECURITY_GROUP_RULES>
  
  # Security groups to attach to EKS managed node groups
  node_security_group_ids = <NODE_SECURITY_GROUP_IDS>
  
  tags = {
    "<PLATFORM_NAME_KEBAB>.cost-allocation.cost-center" = "platform"
    "<PLATFORM_NAME_KEBAB>.metadata.cluster-name"       = local.cluster_name
    "<PLATFORM_NAME_KEBAB>.metadata.owner"              = "${local.cluster_name}-admin"
    "provisioned-by"                                    = "<PLATFORM_NAME_KEBAB>"
  }
  labels = {
    "<PLATFORM_NAME_KEBAB>.cost-allocation.cost-center" = "platform"
    "<PLATFORM_NAME_KEBAB>.metadata.cluster-name"       = local.cluster_name
    "<PLATFORM_NAME_KEBAB>.metadata.owner"              = "${local.cluster_name}-admin"
    "provisioned-by"                                    = "<PLATFORM_NAME_KEBAB>"
  }
}

# Cloud Provider configuration
# <TF_HOSTING_PROVIDER>


module "hosting-provider" {
  source                 = "../modules/cloud_<CLOUD_PROVIDER>"
  cluster_name           = local.cluster_name
  cluster_version        = local.cluster_version
  cluster_network_cidr   = local.cluster_network_cidr
  region                 = local.region
  alert_emails           = local.email
  cluster_ssh_public_key = var.cluster_ssh_public_key
  tags                   = local.tags
  cluster_node_labels    = local.labels
  domain_name            = local.domain_name
  workloads              = var.workloads
  
  # Existing VPC configuration (optional)
  vpc_id             = local.vpc_id
  private_subnet_ids = local.private_subnet_ids
  public_subnet_ids  = local.public_subnet_ids
  intra_subnet_ids   = local.intra_subnet_ids
  database_subnets   = local.database_subnets
  
  # ACM certificate for ALB Ingress Controller / Gateway API
  acm_certificate_arn = local.acm_certificate_arn
  
  # Security groups (optional)
  cluster_security_group_id             = local.cluster_security_group_id
  additional_cluster_security_group_ids = local.additional_cluster_security_group_ids
  
  # CloudWatch configuration
  cloudwatch_log_group_retention_in_days = local.cloudwatch_log_group_retention_in_days
  
  # Node security group additional rules
  node_security_group_additional_rules = local.node_security_group_additional_rules
  
  # Security groups to attach to EKS managed node groups
  node_security_group_ids = local.node_security_group_ids
  
  ## Example of node groups for the AWS cloud hosting provider
  ## Please note that for the  GPU or metal nodes, you need to check node type availability
  ## in your region and send service quota-increasing request to the support
  # node_groups            = [
  #   {
  #     name           = "default"
  #     instance_types = ["m5.large"]
  #     capacity_type  = "on_demand"
  #     min_size       = 3
  #     max_size       = 6
  #     disk_size      = 100
  #     desired_size   = 4
  #   },
  #   # {
  #   #   name           = "ml-node-group"
  #   #   instance_types = ["g5.xlarge"]
  #   #   gpu_enabled    = true
  #   #   capacity_type  = "on_demand"
  #   #   min_size       = 0
  #   #   max_size       = 1
  #   #   desired_size   = 1
  #   # },
  #   # {
  #   #   name           = "metal-node-group"
  #   #   instance_types = ["c5.metal"]
  #   #   gpu_enabled    = false
  #   #   capacity_type  = "on_demand"
  #   #   min_size       = 0
  #   #   max_size       = 1
  #   #   desired_size   = 1
  #   # },
  # ]
}
