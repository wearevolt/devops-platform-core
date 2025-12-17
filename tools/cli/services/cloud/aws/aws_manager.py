import textwrap
from typing import Tuple

from common.tracing_decorator import trace
from common.utils.generators import random_string_generator
from common.utils.os_utils import detect_command_presence
from services.cloud.aws.aws_sdk import AwsSdk
from services.cloud.aws.iam_permissions import vpc_permissions, eks_permissions, s3_permissions, \
    own_iam_permissions, iam_permissions
from services.cloud.cloud_provider_manager import CloudProviderManager

CLI = 'aws'


class AWSManager(CloudProviderManager):
    """AWS wrapper."""

    def __init__(self, region, profile, key, secret):
        self._aws_sdk = AwsSdk(region, profile, key, secret)

    @property
    def region(self) -> str:
        """AWS region"""
        return self._aws_sdk.region

    @property
    def account(self) -> str:
        """AWS account id"""
        return self._aws_sdk.account_id

    @classmethod
    def detect_cli_presence(cls) -> bool:
        """Check whether `name` is on PATH and marked as executable."""
        return detect_command_presence(CLI)

    @trace()
    def create_iac_state_storage(self, name: str, **kwargs: dict) -> Tuple[str, str]:
        """
        Creates cloud-native Terraform remote state storage in AWS.

        This method generates a unique name for an S3 bucket based on the provided 'name' and a random string.
        It then creates the S3 bucket in the specified or default region and enables versioning on the bucket
        for Terraform state files.

        Args:
            name (str): Base name to use for generating the S3 bucket name.
            **kwargs (dict): Additional keyword arguments, where 'region' can be specified for the S3 bucket location.

        Returns:
            Tuple[str, str]: A tuple containing the name of the created S3 bucket and an empty string
            (as the second value is not used in this context).
        """
        region = self.region
        if kwargs and "region" in kwargs:
            region = kwargs["region"]
        tf_backend_storage_name = f'{name}-{random_string_generator()}'.lower()

        self._aws_sdk.create_bucket(tf_backend_storage_name, region)
        self._aws_sdk.enable_bucket_versioning(tf_backend_storage_name, region)

        return tf_backend_storage_name, ""

    @trace()
    def resolve_iac_state_storage(self, name_prefix: str, **kwargs: dict) -> str | None:
        """
        Discover the active Terraform remote state bucket for this platform.
        Prefers buckets that already contain terraform state objects.
        """
        region = self.region
        if kwargs and "region" in kwargs:
            region = kwargs["region"]

        prefix = f"{name_prefix}-"
        try:
            buckets = [b for b in self._aws_sdk.list_buckets() if b.startswith(prefix)]
        except Exception:
            return None

        state_keys = [
            "terraform/hosting_provider/terraform.tfstate",
            "terraform/vcs/terraform.tfstate",
            "terraform/secrets/terraform.tfstate",
            "terraform/users/terraform.tfstate",
            "terraform/core_services/terraform.tfstate",
        ]

        best_bucket = None
        best_score = -1
        for b in buckets:
            if not self._aws_sdk.bucket_exists(b, region=region):
                continue
            score = 0
            for k in state_keys:
                if self._aws_sdk.object_exists(b, k, region=region):
                    score += 1
            if score > best_score:
                best_bucket = b
                best_score = score

        return best_bucket

    @trace()
    def protect_iac_state_storage(self, name: str, identity: str, **kwargs: dict):
        region = self.region
        if kwargs and "region" in kwargs:
            region = kwargs["region"]

        self._aws_sdk.set_bucket_policy(name, identity, region)

    @trace()
    def destroy_iac_state_storage(self, name: str) -> bool:
        """
        Destroy cloud native terraform remote state storage
        """
        return self._aws_sdk.delete_bucket(name)

    @trace()
    def create_iac_backend_snippet(self, location: str, service: str, **kwargs: dict) -> str:
        """
         Generate the Terraform configuration for the Aws backend.

         This function creates a text snippet that can be used as the backend configuration in a Terraform file.
         It uses the AWS S3 backend.

         Args:
             location (str): The name of the storage container
             service (str): The name of the service,
             which is used as part of the key in the backend configuration.

         Returns:
             str: The Terraform backend configuration snippet.
         """
        # TODO: consider replacing with file template
        region = self.region
        if kwargs and "region" in kwargs:
            region = kwargs["region"]

        return textwrap.dedent('''\
          backend "s3" {{
            bucket = "{bucket}"
            key    = "terraform/{service}/terraform.tfstate"
            region  = "{region}"
            encrypt = true
          }}'''.format(bucket=location, region=region, service=service))

    @trace()
    def create_hosting_provider_snippet(self) -> str:
        # TODO: consider replacing with file template
        return textwrap.dedent('''\
        provider "aws" {
          default_tags {
            tags = local.tags
          }
        }''')

    @trace()
    def create_seal_snippet(self, key_id: str, **kwargs) -> str:
        return '''seal "awskms" {{
                  region     = "{region}"
                  kms_key_id = "{kms_key_id}"
                }}'''.format(region=self.region, kms_key_id=key_id)

    @trace()
    def create_k8s_cluster_role_mapping_snippet(self) -> str:
        # TODO: consider replacing with file template
        return "eks.amazonaws.com/role-arn"

    @trace()
    def get_k8s_auth_command(self) -> tuple[str, [str]]:
        args = [
            "--region",
            "<CLUSTER_REGION>",
            "eks",
            "get-token",
            "--cluster-name",
            "<CLUSTER_NAME>",
            "--output",
            "json"
        ]
        return "aws", args

    @trace()
    def get_k8s_token(self, cluster_name: str) -> str:
        token = self._aws_sdk.get_token(cluster_name=cluster_name)
        return token['status']['token']

    @trace()
    def get_eks_cluster_connection_info(self, cluster_name: str) -> dict:
        """Source-of-truth cluster connection info from AWS API (not from cached state)."""
        return self._aws_sdk.describe_eks_cluster(cluster_name=cluster_name, region=self.region)

    @trace()
    def evaluate_permissions(self) -> bool:
        """
        Check if provided credentials have required permissions
        :return: True or False
        """
        missing_permissions = []
        missing_permissions.extend(self._aws_sdk.blocked(vpc_permissions))
        missing_permissions.extend(self._aws_sdk.blocked(eks_permissions))
        missing_permissions.extend(self._aws_sdk.blocked(iam_permissions))
        missing_permissions.extend(self._aws_sdk.blocked(s3_permissions))
        missing_permissions.extend(self._aws_sdk.blocked(own_iam_permissions, [self._aws_sdk.current_user_arn()]))
        return len(missing_permissions) == 0

    @trace()
    def create_ingress_annotations(self) -> str:
        return '''service.beta.kubernetes.io/aws-load-balancer-ssl-ports: "https"
              service.beta.kubernetes.io/aws-load-balancer-connection-idle-timeout: "60"'''

    @trace()
    def create_additional_labels(self) -> str:
        return ""

    @trace()
    def create_sidecar_annotation(self) -> str:
        return ""

    @trace()
    def create_external_secrets_config(self, **kwargs) -> str:
        return ""

    @trace()
    def create_iac_pr_automation_config_snippet(self):
        return '''# aws specific section
      # ----'''

    @trace()
    def create_autoscaler_snippet(self, cluster_name: str, node_groups=[]):
        return '''awsRegion: <CLOUD_REGION>'''

    @trace()
    def create_kubecost_annotation(self):
        return '''amazon-web-services: true'''

    @trace()
    def create_gpu_operator_parameters(self):
        return ''

    @trace()
    def get_cloud_provider_k8s_dns_deployment_name(self) -> str:
        """
        Retrieves the name of the Kubernetes DNS deployment specific to AWS.

        :return: A string "coredns", indicating the DNS deployment name for AWS.
        :rtype: str
        """
        return "coredns"

    def create_ci_artifact_store_config_snippet(self) -> str:
        """
        Creates Cloud Provider specific configuration section for Argo Workflow artifact storage
        :return: Artifact storage configuration section
        """
        return textwrap.dedent('''s3:
      bucket: <CLOUD_BINARY_ARTIFACTS_STORE>
      endpoint: s3.amazonaws.com
      insecure: false
      keyFormat: "{{workflow.parameters.workload-name}}/{{workflow.parameters.tag}}/{{pod.name}}/"
      region: <CLOUD_REGION>
      useSDKCreds: true
      encryptionOptions:
        enableEncryption: false''')

    def create_velero_config_snippet(self) -> str:
        """
        Creates Cloud Provider specific configuration snippet for Velero
        :return: Artifact storage configuration section
        """
        return textwrap.dedent('''configuration:
          backupStorageLocation:
            - name: default
              provider: velero.io/aws
              bucket: <CLOUD_CLUSTER_BACKUPS_STORE>
              config:
                region: <CLOUD_REGION>
          volumeSnapshotLocation:
            - name: default
              provider: velero.io/aws
              config:
                region: <CLOUD_REGION>
        initContainers:
          - name: plugin-for-aws
            image: velero/velero-plugin-for-aws:v1.11.0
            volumeMounts:
              - mountPath: /target
                name: plugins
        credentials:
          useSecret: false''')
