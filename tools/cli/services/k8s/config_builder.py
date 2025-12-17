import pkg_resources
import yaml

from common.const.common_path import LOCAL_FOLDER
from common.tracing_decorator import trace


def repair_kubeconfig_file(kubeconfig_path: str, cluster_name: str | None = None) -> bool:
    """
    Repair a kubeconfig file in-place if it's missing required context entries.

    Common failure we observed: current-context is set but `contexts: []`, which breaks kubernetes client loading.
    Returns True if a change was applied.
    """
    try:
        with open(kubeconfig_path, "r") as f:
            conf = yaml.safe_load(f.read()) or {}
    except Exception:
        return False

    changed = False
    ctxs = conf.get("contexts")
    if ctxs is None:
        conf["contexts"] = []
        ctxs = conf["contexts"]
        changed = True

    # Determine the intended context name
    intended = (cluster_name or conf.get("current-context") or "").strip() or None
    if intended and not conf.get("current-context"):
        conf["current-context"] = intended
        changed = True

    # If contexts is empty, synthesize one based on cluster/user naming
    if intended and isinstance(ctxs, list) and len(ctxs) == 0:
        conf["contexts"] = [{
            "name": intended,
            "context": {
                "cluster": intended,
                "user": intended,
            }
        }]
        changed = True

    if changed:
        try:
            with open(kubeconfig_path, "w") as f:
                f.write(yaml.dump(conf))
            return True
        except Exception:
            return False

    return False


@trace()
def create_k8s_config(command: str, command_args: [], cloud_provider_auth_env_vars: dict, kubeconfig_params: dict,
                      kubeconfig_name: str = "kubeconfig") -> str:
    template_file_path = pkg_resources.resource_filename('services.k8s', "kubeconfig.yaml")

    with open(template_file_path, "r") as file:
        kubeconf = yaml.safe_load(file.read())
        # Defensive: ensure kubeconfig has a valid context entry. If contexts are empty,
        # kubernetes client loading fails with "Expected object with name ... in contexts list".
        cluster_name = (kubeconfig_params.get("<CLUSTER_NAME>") or "").strip()
        if cluster_name and not kubeconf.get("contexts"):
            kubeconf["contexts"] = [{
                "name": "<CLUSTER_NAME>",
                "context": {
                    "cluster": "<CLUSTER_NAME>",
                    "user": "<CLUSTER_NAME>",
                }
            }]
        if cluster_name and not kubeconf.get("current-context"):
            kubeconf["current-context"] = "<CLUSTER_NAME>"

        kubeconf["users"][0]["user"]["exec"]["command"] = command
        kubeconf["users"][0]["user"]["exec"]["args"] = command_args
        envs = []
        for k, v in cloud_provider_auth_env_vars.items():
            if v is not None:
                envs.append({"name": k, "value": v})
        kubeconf["users"][0]["user"]["exec"]["env"] = envs
        data = yaml.dump(kubeconf)
        for k, v in kubeconfig_params.items():
            data = data.replace(k, v)

    path = write_k8s_config(data, kubeconfig_name)
    # Final safeguard: if any tool produced an invalid config (e.g. contexts emptied),
    # repair it in-place so the CLI is idempotent.
    repair_kubeconfig_file(path, cluster_name=(kubeconfig_params.get("<CLUSTER_NAME>") or "").strip() or None)
    return path


@trace()
def write_k8s_config(data, kubeconfig_name: str = "kubeconfig") -> str:
    kubeconfig_path = LOCAL_FOLDER / kubeconfig_name
    with open(kubeconfig_path, "w") as file:
        file.write(data)

    return str(kubeconfig_path)
