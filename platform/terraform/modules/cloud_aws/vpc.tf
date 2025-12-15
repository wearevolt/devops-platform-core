# Create VPC only if vpc_id is not provided
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  # Skip VPC creation if using existing VPC
  create_vpc = local.create_vpc

  name = "${local.name}-vpc"
  cidr = local.vpc_cidr

  azs             = local.azs
  private_subnets = local.create_vpc ? [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 4, k)] : []
  public_subnets  = local.create_vpc ? [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 48)] : []
  intra_subnets   = local.create_vpc ? [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 52)] : []

  enable_nat_gateway = local.create_vpc
  single_nat_gateway = local.create_vpc
  create_igw         = local.create_vpc

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
    "Tier"                   = "public"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
    "Tier"                            = "private"
  }

  intra_subnet_tags = {
    "Tier" = "infra"
  }

}
