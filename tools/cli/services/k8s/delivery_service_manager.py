import json
from typing import Optional

import httpx
from kubernetes import client
from kubernetes import client as k8s_client

from common.const.const import ARGOCD_REGISTRY_APP_PATH, GITOPS_REPOSITORY_URL
from common.const.namespaces import ARGOCD_NAMESPACE
from common.logging_config import logger
from common.retry_decorator import exponential_backoff
from common.utils.k8s_utils import get_kr8s_pod_instance_by_name
from services.k8s.k8s import KubeClient


async def get_argocd_token_via_k8s_portforward(
        user: str,
        password: str,
        k8s_pod: k8s_client.V1Pod,
        kube_config_path: str,
        remote_port: int = 8080,
        local_port: int = 8080,
        max_retries: int = 5
) -> Optional[str]:
    """
    Retrieves an ArgoCD authentication token by establishing a port-forward
    connection using kubectl subprocess (more stable than kr8s).

    :param user: The username for ArgoCD authentication.
    :type user: str
    :param password: The password for ArgoCD authentication.
    :type password: str
    :param k8s_pod: The Kubernetes pod object hosting the ArgoCD service that supports port forwarding.
    :type k8s_pod: k8s_client.V1Pod
    :param kube_config_path: Path to the kubeconfig file for Kubernetes cluster authentication and interaction.
    :type kube_config_path: str
    :param remote_port: The remote port on the Kubernetes pod to forward.
    :type remote_port: int
    :param local_port: The local port to map the remote port's forwarding.
    :type local_port: int
    :param max_retries: Maximum number of retry attempts for port-forward failures.
    :type max_retries: int
    :return: The ArgoCD authentication token if retrieval is successful; otherwise, None.
    :rtype: Optional[str]
    """
    import asyncio
    import subprocess
    import socket
    
    last_error = None
    pod_name = k8s_pod.metadata.name
    
    def find_free_port():
        """Find a free port on localhost."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
    
    for attempt in range(max_retries):
        # Use a random free port to avoid conflicts
        actual_local_port = find_free_port()
        port_forward_process = None
        
        try:
            # Start kubectl port-forward as subprocess
            cmd = [
                "kubectl", "port-forward",
                f"pod/{pod_name}",
                f"{actual_local_port}:{remote_port}",
                "-n", ARGOCD_NAMESPACE,
                "--kubeconfig", kube_config_path
            ]
            logger.info(f"Starting port-forward: {' '.join(cmd)}")
            
            port_forward_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for port-forward to establish
            await asyncio.sleep(3)
            
            # Check if process is still running
            if port_forward_process.poll() is not None:
                stderr = port_forward_process.stderr.read().decode() if port_forward_process.stderr else ""
                raise RuntimeError(f"Port-forward failed to start: {stderr}")
            
            # Try to get token
            token = await get_argocd_token(user, password, f'localhost:{actual_local_port}', max_retries=3)
            if token:
                return token
            
        except Exception as e:
            last_error = e
            logger.warning(f"ArgoCD port-forward failed (attempt {attempt + 1}/{max_retries}): {e}")
        finally:
            # Always terminate port-forward process
            if port_forward_process:
                port_forward_process.terminate()
                try:
                    port_forward_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    port_forward_process.kill()
        
        if attempt < max_retries - 1:
            await asyncio.sleep(5)  # Wait before retry
    
    if last_error:
        raise last_error
    return None


async def get_argocd_token(user: str, password: str, endpoint: str = "localhost:8080", max_retries: int = 3) -> Optional[str]:
    """
    Asynchronously retrieves an ArgoCD authentication token from a specified endpoint.
    Uses HTTPS with SSL verification disabled (ArgoCD uses self-signed certs).

    :param user: The username for authentication with ArgoCD.
    :type user: str
    :param password: The password for authentication with ArgoCD.
    :type password: str
    :param endpoint: The endpoint URL where the ArgoCD API is available, defaulting to "localhost:8080".
    :type endpoint: str
    :param max_retries: Maximum number of retry attempts for transient errors.
    :type max_retries: int
    :return: The ArgoCD authentication token if the request succeeds and the user is authenticated; otherwise, None.
    :rtype: Optional[str]
    """
    import asyncio
    import ssl
    
    last_error = None
    
    # Create SSL context that doesn't verify certificates
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    for attempt in range(max_retries):
        # ArgoCD server uses HTTPS with self-signed certificate
        async with httpx.AsyncClient(verify=False, timeout=30.0) as httpx_client:
            try:
                # Try HTTPS first (ArgoCD default)
                response = await httpx_client.post(
                    f"https://{endpoint}/api/v1/session",
                    headers={"Content-Type": "application/json"},
                    content=json.dumps({"username": user, "password": password})
                )
                if response.status_code == 404:
                    return None
                elif response.is_success:
                    return response.json()["token"]
                else:
                    logger.warning(f"ArgoCD returned status {response.status_code}: {response.text}")
            except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
                # SSL/connection error - try HTTP as fallback
                logger.debug(f"HTTPS failed, trying HTTP: {e}")
                try:
                    response = await httpx_client.post(
                        f"http://{endpoint}/api/v1/session",
                        headers={"Content-Type": "application/json"},
                        content=json.dumps({"username": user, "password": password}),
                        follow_redirects=True  # Follow redirects to HTTPS
                    )
                    if response.status_code == 404:
                        return None
                    elif response.is_success:
                        return response.json()["token"]
                except Exception as http_e:
                    last_error = http_e
                    logger.warning(f"HTTP also failed: {http_e}")
            except httpx.ReadError as e:
                # Connection was broken during read - retry
                last_error = e
                logger.warning(f"ArgoCD connection read error (attempt {attempt + 1}/{max_retries}): {e}")
            except httpx.HTTPStatusError as e:
                raise e
        
        # Wait before retry
        if attempt < max_retries - 1:
            await asyncio.sleep(3)
    
    if last_error:
        raise last_error
    return None


async def delete_application_via_k8s_portforward(
        app_name: str,
        user: str,
        password: str,
        k8s_pod: k8s_client.V1Pod,
        kube_config_path: str,
        remote_port: int = 8080,
        local_port: int = 8080
) -> Optional[bool]:
    """
    Asynchronously retrieves an ArgoCD token and deletes an application from the ArgoCD server by
    port forwarding a Kubernetes pod's port to a local port. This method first obtains an authentication
    token by forwarding the ArgoCD API service's port to a local port and then uses this token to
    send a deletion request to the ArgoCD API.

    :param app_name: The name of the application to be deleted.
    :type app_name: str
    :param user: The username used for ArgoCD token retrieval.
    :type user: str
    :param password: The password used for ArgoCD token retrieval.
    :type password: str
    :param k8s_pod: The Kubernetes pod hosting the ArgoCD service that supports port forwarding.
    :type k8s_pod: k8s_client.V1Pod
    :param kube_config_path: Path to the kubeconfig file for Kubernetes cluster authentication.
    :type kube_config_path: str
    :param remote_port: The port on the Kubernetes pod to be forwarded.
    :type remote_port: int
    :param local_port: The local port to which the remote port's forwarding will be mapped.
    :type local_port: int
    :return: True if the application deletion is successful; otherwise, None.
    :rtype: Optional[bool]
    """
    kr8s_pod = await get_kr8s_pod_instance_by_name(
        pod_name=k8s_pod.metadata.name,
        namespace=ARGOCD_NAMESPACE,
        kubeconfig=kube_config_path
    )

    async with kr8s_pod.portforward(remote_port=remote_port, local_port=local_port):
        # Retrieve the ArgoCD token
        token = await get_argocd_token(user, password, f'localhost:{local_port}')
        if not token:
            return None

        # Use the token to request the deletion of the application
        return await delete_application(app_name, token, f'localhost:{local_port}')


@exponential_backoff(base_delay=5)
async def delete_application(app_name: str, token: str, endpoint: str = "localhost:8080") -> Optional[bool]:
    """
    Asynchronously deletes an application from the ArgoCD server via a specified endpoint.
    Tries HTTPS first, falls back to HTTP if HTTPS fails.

    :param app_name: The name of the application to delete.
    :type app_name: str
    :param token: The ArgoCD authentication token.
    :type token: str
    :param endpoint: The endpoint URL where the ArgoCD API is accessed, defaulting to "localhost:8080".
    :type endpoint: str
    :return: True if the application was successfully deleted; otherwise, None.
    :rtype: Optional[bool]
    """
    async with httpx.AsyncClient(verify=False, timeout=30.0) as httpx_client:
        for protocol in ["https", "http"]:
            try:
                response = await httpx_client.delete(
                    f"{protocol}://{endpoint}/api/v1/applications/{app_name}?cascade=true",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}"
                    }
                )
                return response.is_success
            except (httpx.ConnectError, httpx.RemoteProtocolError):
                continue
            except httpx.HTTPStatusError as e:
                raise e
    return None


class DeliveryServiceManager:
    def __init__(self, k8s_client: KubeClient, argocd_namespace: str = ARGOCD_NAMESPACE):
        self._k8s_client = k8s_client
        self._group = "argoproj.io"
        self._version = "v1alpha1"
        self._namespace = argocd_namespace

    def _create_argocd_object(self, argo_obj, plurals):
        return self._k8s_client.create_custom_object(self._namespace, argo_obj, self._group, self._version, plurals)

    def create_project(self, project_name: str, repos=None):
        if repos is None:
            repos = ["*"]
        argo_proj_cr = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "AppProject",
            "metadata": {
                "name": project_name,
                "namespace": self._namespace,
                # Finalizer that ensures that project is not deleted until it is not referenced by any application
                "finalizers": ["argocd.argoproj.io/finalizer"]
            },
            "spec": {
                "description": "CG DevX platform core services",
                # allow manifests only from gitops repo
                "sourceRepos": repos,
                # Only permit applications to deploy in the same cluster
                "destinations": [
                    {
                        "namespace": "*",
                        "name": "*",
                        "server": "*"  # https://kubernetes.default.svc
                    }
                ],
                "clusterResourceWhitelist": [
                    {
                        "group": "*",
                        "kind": "*"
                    }
                ],
                "namespaceResourceWhitelist": [
                    {
                        "group": "*",
                        "kind": "*"
                    }
                ]
            }
        }

        return self._create_argocd_object(argo_proj_cr, "appprojects")

    def create_core_application(self, project_name: str, repo_url: str, exclude: str = ""):
        argo_app_cr = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": "registry",
                "namespace": self._namespace,
                "annotations": {"argocd.argoproj.io/sync-wave": "1"},
            },
            "spec": {
                "source": {
                    "repoURL": repo_url,
                    "path": ARGOCD_REGISTRY_APP_PATH,
                    "targetRevision": "HEAD"
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": self._namespace,
                },
                "project": project_name,
                "syncPolicy": {
                    "automated": {
                        "prune": True,
                        "selfHeal": True,
                    },
                    "syncOptions": ["CreateNamespace=true"],
                    "retry": {
                        "limit": 5,
                        "backoff": {
                            "duration": "5s",
                            "factor": 2,
                            "maxDuration": "5m0s",
                        },
                    },
                },
            },
        }

        if exclude:
            argo_app_cr["spec"]["source"]["directory"] = {"exclude": f"{{{exclude}}}"}

        return self._create_argocd_object(argo_app_cr, "applications")

    def create_argocd_bootstrap_job(self, sa_name: str):
        """
        Creates ArgoCD bootstrap job
        """
        image = "bitnami/kubectl"
        manifest_path = f"{GITOPS_REPOSITORY_URL}/platform/installation-manifests/argocd?ref=main"

        bootstrap_entry_point = ["/bin/sh", "-c", f"kubectl apply -k '{manifest_path}'"]

        job_name = "kustomize-apply-argocd"

        body = client.V1Job(metadata=client.V1ObjectMeta(name=job_name, namespace=self._namespace),
                            spec=client.V1JobSpec(template=client.V1PodTemplateSpec(
                                spec=client.V1PodSpec(
                                    containers=[
                                        client.V1Container(name="main", image=image,
                                                           command=bootstrap_entry_point)],
                                    service_account_name=sa_name,
                                    restart_policy="Never")),
                                backoff_limit=1))

        return self._k8s_client.create_job(self._namespace, job_name, body)

    def turn_off_app_sync(self, name: str):
        from kubernetes.client.exceptions import ApiException
        sync_policy_patch = [{
            "op": "remove",
            "path": "/spec/syncPolicy",
            "value": ""
        }]
        try:
            return self._k8s_client.patch_custom_object(self._namespace, name, sync_policy_patch, self._group,
                                                        self._version, "applications")
        except ApiException as e:
            if e.status in (404, 422):
                # 404 = app not found, 422 = syncPolicy already removed
                logger.debug(f"Application {name}: skipping sync disable (status {e.status})")
                return None
            raise

    def delete_app(self, name: str):
        from kubernetes.client.exceptions import ApiException
        try:
            return self._k8s_client.remove_custom_object(self._namespace, name, self._group, self._version, "applications")
        except ApiException as e:
            if e.status == 404:
                logger.debug(f"Application {name} not found, skipping deletion")
                return None
            raise
