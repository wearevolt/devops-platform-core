"""
Helm wrapper for CLI operations.
"""
import subprocess
from typing import Dict, Optional, List
from common.logging_config import logger
from common.tracing_decorator import trace


class HelmWrapper:
    """Wrapper for Helm CLI commands."""
    
    def __init__(self, kubeconfig_path: Optional[str] = None):
        """
        Initialize HelmWrapper.
        
        :param kubeconfig_path: Path to kubeconfig file
        """
        self._kubeconfig = kubeconfig_path
    
    def _run_helm(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Run helm command with given arguments.
        
        :param args: List of arguments for helm command
        :param check: Whether to raise exception on non-zero exit code
        :return: CompletedProcess instance
        """
        cmd = ["helm"] + args
        if self._kubeconfig:
            cmd.extend(["--kubeconfig", self._kubeconfig])
        
        logger.info(f"Running helm command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Helm command failed: {result.stderr}")
            if check:
                raise RuntimeError(f"Helm command failed: {result.stderr}")
        
        return result
    
    @trace()
    def repo_add(self, name: str, url: str) -> bool:
        """
        Add a Helm repository.
        
        :param name: Repository name
        :param url: Repository URL
        :return: True if successful
        """
        try:
            self._run_helm(["repo", "add", name, url], check=False)
            self._run_helm(["repo", "update"])
            return True
        except Exception as e:
            logger.error(f"Failed to add helm repo: {e}")
            return False
    
    @trace()
    def install_or_upgrade(
        self,
        release_name: str,
        chart: str,
        namespace: str,
        values: Optional[Dict] = None,
        set_values: Optional[Dict] = None,
        version: Optional[str] = None,
        wait: bool = True,
        timeout: str = "10m",
        create_namespace: bool = True
    ) -> bool:
        """
        Install or upgrade a Helm release.
        
        :param release_name: Name of the release
        :param chart: Chart name (repo/chart or path)
        :param namespace: Kubernetes namespace
        :param values: Values dict to pass as --values (will be written to temp file)
        :param set_values: Values to pass as --set key=value
        :param version: Chart version
        :param wait: Wait for resources to be ready
        :param timeout: Timeout for wait
        :param create_namespace: Create namespace if it doesn't exist
        :return: True if successful
        """
        args = [
            "upgrade", "--install",
            release_name, chart,
            "--namespace", namespace
        ]
        
        if create_namespace:
            args.append("--create-namespace")
        
        if version:
            args.extend(["--version", version])
        
        if wait:
            args.append("--wait")
            args.extend(["--timeout", timeout])
        
        # Process set_values
        if set_values:
            for key, value in set_values.items():
                args.extend(["--set", f"{key}={value}"])
        
        try:
            result = self._run_helm(args)
            logger.info(f"Helm release {release_name} installed/upgraded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to install/upgrade helm release {release_name}: {e}")
            return False
    
    @trace()
    def install_aws_load_balancer_controller(
        self,
        cluster_name: str,
        region: str,
        vpc_id: str,
        service_account_role_arn: str,
        version: str = "1.13.4",
        image_tag: str = "v2.11.0"
    ) -> bool:
        """
        Install AWS Load Balancer Controller.
        
        :param cluster_name: EKS cluster name
        :param region: AWS region
        :param vpc_id: VPC ID
        :param service_account_role_arn: IAM role ARN for service account
        :param version: Helm chart version
        :param image_tag: Controller image tag
        :return: True if successful
        """
        # Add EKS charts repository
        self.repo_add("eks", "https://aws.github.io/eks-charts")
        
        set_values = {
            "clusterName": cluster_name,
            "region": region,
            "vpcId": vpc_id,
            "serviceAccount.create": "true",
            "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn": service_account_role_arn,
            "replicaCount": "2",
            "image.tag": image_tag
        }
        
        return self.install_or_upgrade(
            release_name="aws-load-balancer-controller",
            chart="eks/aws-load-balancer-controller",
            namespace="kube-system",
            set_values=set_values,
            version=version,
            wait=True,
            timeout="5m"
        )

