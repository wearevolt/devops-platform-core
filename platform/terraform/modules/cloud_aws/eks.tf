# EKS Cluster Module
# https://github.com/terraform-aws-modules/terraform-aws-eks
# Version 21.x API

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.10.0"

  # Cluster configuration
  name               = local.name
  kubernetes_version = local.cluster_version

  # Network configuration
  vpc_id                   = local.effective_vpc_id
  subnet_ids               = local.effective_private_subnets
  control_plane_subnet_ids = local.effective_private_subnets

  # Endpoint access
  endpoint_public_access  = var.endpoint_public_access
  endpoint_private_access = var.endpoint_private_access

  # Enable OIDC provider for IRSA (required for: Karpenter, EBS CSI Driver, ALB Controller, etc.)
  enable_irsa = true

  # CloudWatch Logs configuration
  cloudwatch_log_group_retention_in_days = var.cloudwatch_log_group_retention_in_days
  enabled_log_types                      = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  # KMS configuration
  kms_key_enable_default_policy   = true
  kms_key_deletion_window_in_days = 7
  kms_key_administrators          = ["*"]

  # Cluster addons
  addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent              = true
      before_compute           = true
      service_account_role_arn = module.vpc_cni_irsa.arn
      configuration_values = jsonencode({
        env = {
          # Reference docs https://docs.aws.amazon.com/eks/latest/userguide/cni-increase-ip-addresses.html
          ENABLE_PREFIX_DELEGATION = "true"
          WARM_PREFIX_TARGET       = "1"
        }
      })
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa_role.arn
      configuration_values = jsonencode({
        defaultStorageClass = {
          enabled = true
        }
      })
    }
  }

  # Security Groups
  security_group_id             = var.cluster_security_group_id != "" ? var.cluster_security_group_id : null
  additional_security_group_ids = var.additional_cluster_security_group_ids

  # Node security group - always create, custom SGs will be added via vpc_security_group_ids in node groups
  create_node_security_group           = true
  node_security_group_additional_rules = var.node_security_group_additional_rules

  # Cluster creator admin permissions
  enable_cluster_creator_admin_permissions = true

  # Auth config
  authentication_mode = "API_AND_CONFIG_MAP"

  # Access entries for GitHub OIDC role (CI/CD access)
  # Cluster creator already has admin access via enable_cluster_creator_admin_permissions = true
  access_entries = {
    git-assumable = {
      kubernetes_groups = []
      principal_arn     = "arn:aws:iam::${local.aws_account}:role/iam-github-oidc-role"
      policy_associations = {
        admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }

  # Node groups (defaults are set per group in v21.x)
  # Module will automatically combine: cluster_primary_sg + node_sg + vpc_security_group_ids
  eks_managed_node_groups = (local.node_group_type == "EKS") ? {
    for k, v in local.eks_node_groups : k => merge(v, {
      attach_cluster_primary_security_group = true
      disk_size                             = 100
      vpc_security_group_ids                = var.node_security_group_ids
    })
  } : {}

  # Self-managed node groups (if needed)
  self_managed_node_groups = (local.node_group_type == "SELF") ? local.sm_node_groups : {}

  tags = local.tags
}
