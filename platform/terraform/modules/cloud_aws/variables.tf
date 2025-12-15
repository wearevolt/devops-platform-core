variable "region" {
  type        = string
  default     = "eu-west-1"
  description = "Specifies the regions"
}

variable "cluster_network_cidr" {
  type    = string
  default = "10.0.0.0/16"
  validation {
    condition     = can(cidrnetmask(var.cluster_network_cidr))
    error_message = "Must be a valid IPv4 CIDR block address."
  }
}

# Existing VPC configuration (optional)
# If vpc_id is provided, the module will use existing VPC instead of creating a new one
variable "vpc_id" {
  type        = string
  default     = ""
  description = "(Optional) ID of existing VPC to use. If empty, a new VPC will be created."
}

variable "private_subnet_ids" {
  type        = list(string)
  default     = []
  description = "(Optional) List of existing private subnet IDs for EKS worker nodes. Required if vpc_id is set."
}

variable "public_subnet_ids" {
  type        = list(string)
  default     = []
  description = "(Optional) List of existing public subnet IDs for load balancers. Required if vpc_id is set."
}

variable "intra_subnet_ids" {
  type        = list(string)
  default     = []
  description = "(Optional) List of existing intra/control plane subnet IDs. If empty and vpc_id is set, private_subnet_ids will be used."
}

variable "database_subnets" {
  type        = list(string)
  default     = []
  description = "(Optional) List of existing database subnet IDs. If empty and vpc_id is set, private_subnet_ids will be used."
}

# ACM Certificate for ALB Ingress Controller / Gateway API
variable "acm_certificate_arn" {
  type        = string
  default     = ""
  description = "(Optional) ARN of ACM certificate for ALB Ingress Controller and Gateway API"
}

# Security Groups for EKS
variable "cluster_security_group_id" {
  type        = string
  default     = ""
  description = "(Optional) Existing security group ID to use for EKS cluster. If empty, a new one will be created."
}

variable "additional_cluster_security_group_ids" {
  type        = list(string)
  default     = []
  description = "(Optional) List of additional security group IDs to attach to the EKS cluster"
}

variable "node_security_group_additional_rules" {
  type        = any
  default     = {}
  description = "(Optional) Additional security group rules for EKS nodes"
}

variable "node_security_group_ids" {
  type        = list(string)
  default     = []
  description = "(Optional) List of security group IDs to attach to EKS managed node groups"
}

# CloudWatch configuration
variable "cloudwatch_log_group_retention_in_days" {
  type        = number
  default     = 7
  description = "(Optional) Retention period for CloudWatch log group in days"
}

# EKS endpoint access
variable "endpoint_public_access" {
  type        = bool
  default     = true
  description = "(Optional) Whether the EKS cluster endpoint is publicly accessible"
}

variable "endpoint_private_access" {
  type        = bool
  default     = true
  description = "(Optional) Whether the EKS cluster endpoint is privately accessible"
}

variable "az_count" {
  type    = number
  default = 3
  validation {
    condition     = var.az_count > 0
    error_message = "Must be > 0"
  }
}

variable "cluster_name" {
  type        = string
  description = "(Required) Specifies the name of the EKS cluster."
  validation {
    condition     = (length(var.cluster_name) <= 16) && (length(var.cluster_name) >= 2)
    error_message = "Must be between 2 and 16 symbols long"
  }
  validation {
    condition     = can(regex("[a-z0-9]+(?:-[a-z0-9]+)*", var.cluster_name))
    error_message = "Invalid input, string should be in kebab-case."
  }
}

variable "cluster_version" {
  type        = string
  default     = "1.34"
  description = "(Optional) Specifies the EKS Kubernetes version"
}

variable "node_group_type" {
  type    = string
  default = "EKS"
  validation {
    condition     = contains(["EKS", "SELF"], var.node_group_type)
    error_message = "Can be \"EKS\" for eks-managed  or \"SELF\" for self-managed node groups."
  }
}

variable "node_groups" {
  type = list(object({
    name           = optional(string, "default")
    instance_types = optional(list(string), ["m5.large"])
    capacity_type  = optional(string, "on_demand")
    min_size       = optional(number, 3)
    max_size       = optional(number, 6)
    desired_size   = optional(number, 4)
    disk_size      = optional(number, 50)
    gpu_enabled    = optional(bool, false)
  }))
  default = [
    {
      name           = "default"
      instance_types = ["m5.large"]
      capacity_type  = "on_demand"
      min_size       = 3
      max_size       = 6
      desired_size   = 4
    },
  ]
}

variable "cluster_node_labels" {
  type        = map(any)
  default     = {}
  description = "(Optional) EKS node labels"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "(Optional) Specifies the AWS resource tags"
}

variable "alert_emails" {
  type    = list(string)
  default = []
}

variable "cluster_ssh_public_key" {
  description = "(Optional) SSH public key to access worker nodes."
  type        = string
  default     = ""
}

variable "domain_name" {
  type        = string
  description = "Specifies the platform domain name"
}

variable "workloads" {
  description = "Workloads configuration"
  type        = map(object({
    description = optional(string, "")
  }))
  default = {}
}
