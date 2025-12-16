"""
Version management module for DevOps Platform.
Loads component versions from versions.yaml file.
"""
from pathlib import Path
from typing import Dict, Any

import yaml


def load_versions() -> Dict[str, Any]:
    """Load versions from versions.yaml file."""
    versions_file = Path(__file__).parent / "versions.yaml"
    
    if not versions_file.exists():
        raise FileNotFoundError(f"Versions file not found: {versions_file}")
    
    with open(versions_file, 'r') as f:
        return yaml.safe_load(f)


# Load versions once at module import
_versions = load_versions()

# Kubernetes tools
KUBECTL_VERSION = _versions.get("kubectl", "1.32.0")
TERRAFORM_VERSION = _versions.get("terraform", "1.11.4")

# Terraform providers
GITLAB_TF_REQUIRED_PROVIDER_VERSION = _versions.get("gitlab_provider", "18.2.0")
GITHUB_TF_REQUIRED_PROVIDER_VERSION = _versions.get("github_provider", "6.9.0")

# ArgoCD and GitOps
ARGOCD_VERSION = _versions.get("argocd", "7.7.16")
ARGO_WORKFLOWS_VERSION = _versions.get("argo_workflows", "0.45.15")

# Core services
VAULT_VERSION = _versions.get("vault", "0.26.1")
EXTERNAL_SECRETS_VERSION = _versions.get("external_secrets", "0.16.0")
EXTERNAL_DNS_VERSION = _versions.get("external_dns", "1.16.1")
CERT_MANAGER_VERSION = _versions.get("cert_manager", "1.17.2")
INGRESS_NGINX_VERSION = _versions.get("ingress_nginx", "4.12.2")

# AWS Load Balancer Controller
AWS_LOAD_BALANCER_CONTROLLER_VERSION = _versions.get("aws_load_balancer_controller", "1.13.4")
AWS_LOAD_BALANCER_CONTROLLER_IMAGE_TAG = _versions.get("aws_load_balancer_controller_image_tag", "v2.11.0")

# Monitoring & Observability
KUBE_PROMETHEUS_STACK_VERSION = _versions.get("kube_prometheus_stack", "72.6.2")
PROMETHEUS_OPERATOR_CRDS_VERSION = _versions.get("prometheus_operator_crds", "20.0.0")
TRIVY_OPERATOR_VERSION = _versions.get("trivy_operator", "0.28.1")
LOKI_VERSION = _versions.get("loki", "6.30.0")
PROMTAIL_VERSION = _versions.get("promtail", "6.16.6")

# CI/CD Runners
ACTIONS_RUNNER_CONTROLLER_VERSION = _versions.get("actions_runner_controller", "0.23.7")
GITLAB_RUNNER_VERSION = _versions.get("gitlab_runner", "0.77.2")

# IaC & Automation
ATLANTIS_VERSION = _versions.get("atlantis", "5.17.2")

# Registry & Artifacts
HARBOR_VERSION = _versions.get("harbor", "v1.16.3")

# Code Quality
SONARQUBE_VERSION = _versions.get("sonarqube", "10.2.0")

# Developer Portal
BACKSTAGE_VERSION = _versions.get("backstage", "1.6.0")

# Utilities
RELOADER_VERSION = _versions.get("reloader", "v2.1.3")

# Scalers
CLUSTER_AUTOSCALER_VERSION = _versions.get("cluster_autoscaler", "9.46.6")
KEDA_VERSION = _versions.get("keda", "v2.17.1")

# Cost Management
KUBECOST_VERSION = _versions.get("kubecost", "2.7.2")

# Security
KYVERNO_VERSION = _versions.get("kyverno", "v3.4.1")
KYVERNO_POLICIES_VERSION = _versions.get("kyverno_policies", "v3.4.1")
POLICY_REPORTER_VERSION = _versions.get("policy_reporter", "v3.1.4")
TRACEE_VERSION = _versions.get("tracee", "0.23.1")

# Backup
VELERO_VERSION = _versions.get("velero", "7.2.1")

# ML/GPU
GPU_OPERATOR_VERSION = _versions.get("gpu_operator", "v24.3.0")

# Third-party integrations
PERFECTSCALE_EXPORTER_VERSION = _versions.get("perfectscale_exporter", "v1.0.41")
PERFECTSCALE_AUTOSCALER_VERSION = _versions.get("perfectscale_autoscaler", "v1.0.10")


def get_version(component: str) -> str:
    """Get version for a specific component."""
    return _versions.get(component, "unknown")


def get_all_versions() -> Dict[str, Any]:
    """Get all versions as a dictionary."""
    return _versions.copy()
