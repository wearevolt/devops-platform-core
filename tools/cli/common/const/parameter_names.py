OWNER_EMAIL = 'email'
CLOUD_PROVIDER = 'cloud-provider'
CLOUD_PROFILE = 'cloud-profile'
CLOUD_ACCOUNT_ACCESS_KEY = 'cloud-account-key'
CLOUD_ACCOUNT_ACCESS_SECRET = 'cloud-account-secret'
CLOUD_REGION = 'cloud-region'
PRIMARY_CLUSTER_NAME = 'cluster-name'
CLUSTER_VERSION = 'cluster-version'
CLUSTER_NETWORK_CIDR = 'cluster-network-cidr'
PLATFORM_NAME = 'platform-name'

# Existing VPC configuration (optional)
VPC_ID = 'vpc-id'
PRIVATE_SUBNET_IDS = 'private-subnet-ids'
PUBLIC_SUBNET_IDS = 'public-subnet-ids'
INTRA_SUBNET_IDS = 'intra-subnet-ids'
DATABASE_SUBNET_IDS = 'database-subnet-ids'

# ACM certificate for ALB Ingress Controller / Gateway API
ACM_CERTIFICATE_ARN = 'acm-certificate-arn'

# ALB Ingress configuration
ALB_INGRESS_GROUP_NAME = 'alb-ingress-group-name'
ALB_SECURITY_GROUPS = 'alb-security-groups'

# Security groups (optional)
CLUSTER_SECURITY_GROUP_ID = 'cluster-security-group-id'
ADDITIONAL_CLUSTER_SECURITY_GROUP_IDS = 'additional-cluster-security-group-ids'
NODE_SECURITY_GROUP_RULES = 'node-security-group-rules'

# CloudWatch configuration
CLOUDWATCH_LOG_RETENTION_DAYS = 'cloudwatch-log-retention-days'

DNS_REGISTRAR = 'dns-registrar'
DNS_REGISTRAR_ACCESS_TOKEN = 'dns-registrar-token'
DNS_REGISTRAR_ACCESS_KEY = 'dns-registrar-key'
DNS_REGISTRAR_ACCESS_SECRET = 'dns-registrar-secret'
DOMAIN_NAME = 'domain-name'
GIT_PROVIDER = 'git-provider'
GIT_ORGANIZATION_NAME = 'git-org'
GIT_ACCESS_TOKEN = 'git-access-token'
GITOPS_REPOSITORY_NAME = 'gitops-repo-name'
GITOPS_REPOSITORY_TEMPLATE_URL = 'gitops-template-url'
GITOPS_REPOSITORY_TEMPLATE_BRANCH = 'gitops-template-branch'
DEMO_WORKLOAD = 'setup-demo-workload'
OPTIONAL_SERVICES = 'optional-services'
IMAGE_REGISTRY_AUTH = 'image-registry-auth'
