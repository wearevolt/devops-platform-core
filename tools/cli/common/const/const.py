# Import versions from centralized versions module
from common.versions import (
    KUBECTL_VERSION,
    TERRAFORM_VERSION,
    GITLAB_TF_REQUIRED_PROVIDER_VERSION,
    GITHUB_TF_REQUIRED_PROVIDER_VERSION,
)

DEFAULT_ENUM_VALUE = "unknown"
GITOPS_REPOSITORY_URL = "https://github.com/wearevolt/devops-platform-core.git"
GITOPS_REPOSITORY_MAIN_BRANCH = "main"
GITOPS_REPOSITORY_BRANCH = "main"
STATE_INPUT_PARAMS = "input"
STATE_INTERNAL_PARAMS = "internal"
STATE_PARAMS = "params"
STATE_FRAGMENTS = "fragments"
STATE_CHECKPOINTS = "checkpoints"
FALLBACK_AUTHOR_NAME = "wearevolt-bot"
PLATFORM_USER_NAME = "wearevolt-bot"
FALLBACK_AUTHOR_EMAIL = "devops@wearevolt.com"
ARGOCD_REGISTRY_APP_PATH = "gitops-pipelines/delivery/clusters/cc-cluster/core-services"
# Note: KUBECTL_VERSION, TERRAFORM_VERSION, etc. are imported from common.versions
WL_REPOSITORY_URL = "https://github.com/wearevolt/devops-wl-template.git"
WL_REPOSITORY_BRANCH = "main"
WL_PR_BRANCH_NAME_PREFIX = "feature/"
WL_GITOPS_REPOSITORY_URL = "https://github.com/wearevolt/devops-wl-gitops-template.git"
WL_GITOPS_REPOSITORY_BRANCH = "main"
WL_SERVICE_NAME = "default-service"
