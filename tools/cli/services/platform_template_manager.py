import os
import pathlib
import shutil
from pathlib import Path
from urllib.error import HTTPError

import requests
from ghrepo import GHRepo
from git import Repo, RemoteProgress, GitError, Actor
from git.exc import GitCommandError

from common.const.common_path import LOCAL_TF_FOLDER, LOCAL_GITOPS_FOLDER
from common.const.const import GITOPS_REPOSITORY_URL, GITOPS_REPOSITORY_BRANCH
from common.enums.git_providers import GitProviders
from common.logging_config import logger
from common.state_store import StateStore
from common.tracing_decorator import trace


class GitOpsTemplateManager:
    """CG DevX Git repo templates manager."""

    def __init__(self, gitops_template_url: str = None, gitops_template_branch: str = None, token=None):
        if gitops_template_url is None:
            self._url = GITOPS_REPOSITORY_URL
        else:
            self._url = gitops_template_url

        if gitops_template_branch is None:
            self._branch = GITOPS_REPOSITORY_BRANCH
        else:
            self._branch = gitops_template_branch

        # TODO: DEBUG, remove
        self._token = token

    @trace()
    def check_repository_existence(self):
        """
        Check if the repository exists
        :return: True or False
        """
        repo = GHRepo.parse(self._url)
        headers = {}
        if self._token is not None:
            headers['Authorization'] = f'token {self._token}'

        try:
            response = requests.get(f'{repo.api_url}/branches/{self._branch}',
                                    headers=headers)
            if response.status_code == requests.codes["not_found"]:
                return False
            elif response.ok:
                return True
        except HTTPError as e:
            raise e

    @trace()
    def clone(self):
        temp_folder = LOCAL_GITOPS_FOLDER / ".tmp"

        if os.path.exists(LOCAL_GITOPS_FOLDER):
            shutil.rmtree(LOCAL_GITOPS_FOLDER)

        if os.environ.get("CGDEVX_CLI_CLONE_LOCAL", False):
            source_dir = pathlib.Path().resolve().parent
            shutil.copytree(source_dir, temp_folder)
            return

        os.makedirs(temp_folder)
        try:
            repo = Repo.clone_from(self._url, temp_folder, progress=ProgressPrinter(), branch=self._branch)
        except GitError as e:
            raise e

    @staticmethod
    def _parse_github_repo_from_remote(remote_url: str):
        """
        Parse owner/repo from common GitHub remote URL formats.
        Supports:
          - git@github.com:OWNER/REPO.git
          - https://github.com/OWNER/REPO(.git)
        """
        import re

        # SSH
        m = re.match(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>.+?)(?:\.git)?$", remote_url)
        if m:
            return m.group("owner"), m.group("repo")

        # HTTPS
        m = re.match(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>.+?)(?:\.git)?/?$", remote_url)
        if m:
            return m.group("owner"), m.group("repo")

        return None, None

    @staticmethod
    def _create_github_pr_and_try_merge(
        remote_url: str,
        head_branch: str,
        token: str,
        title: str,
        body: str,
        base_branch: str = "main",
    ):
        """
        Create a PR on GitHub and attempt to merge it immediately.
        Returns (pr_number, merged: bool). Raises on hard failures (e.g., invalid token).
        """
        owner, repo = GitOpsTemplateManager._parse_github_repo_from_remote(remote_url)
        if not owner or not repo:
            raise Exception(f"Cannot parse GitHub repo from remote URL: {remote_url}")

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        # GitHub expects head in "OWNER:branch" form for same-org repos.
        head = f"{owner}:{head_branch}"

        # Create PR
        pr_create = requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers,
            json={
                "title": title,
                "head": head,
                "base": base_branch,
                "body": body,
                "maintainer_can_modify": True,
            },
            timeout=30,
        )

        # If PR already exists, GitHub returns 422. Try to find existing open PR for this branch.
        if pr_create.status_code == 422:
            prs = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers=headers,
                params={"state": "open", "base": base_branch, "per_page": 50},
                timeout=30,
            )
            prs.raise_for_status()
            for pr in prs.json():
                if pr.get("head", {}).get("ref") == head_branch:
                    pr_number = pr["number"]
                    break
            else:
                # Include create response for easier debugging
                raise Exception(
                    f"PR create returned 422 but no existing PR found for branch '{head_branch}'. "
                    f"Create response: {pr_create.text}"
                )
        else:
            pr_create.raise_for_status()
            pr_number = pr_create.json()["number"]

        # Try to merge PR (best effort)
        merge = requests.put(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/merge",
            headers=headers,
            json={"merge_method": "squash"},
            timeout=30,
        )
        if merge.status_code in (200, 201):
            return pr_number, True

        # Not mergeable due to required checks/reviews, etc.
        logger.warning(f"PR #{pr_number} created but could not be auto-merged: {merge.status_code} {merge.text}")
        return pr_number, False

    @staticmethod
    @trace()
    def upload(
        path: str,
        key_path: str,
        git_user_name: str,
        git_user_email: str,
        git_provider: GitProviders = None,
        git_access_token: str = None,
    ):

        if not os.path.exists(LOCAL_GITOPS_FOLDER):
            raise Exception("GitOps repo does not exist")

        try:
            ssh_cmd = f'ssh -o StrictHostKeyChecking=no -i {key_path}'

            # IMPORTANT: a PR requires the branch to share history with main.
            # Our generated folder (LOCAL_GITOPS_FOLDER) is not a clone; it's a rendered tree.
            # So we clone origin/main into a temp dir, overlay the rendered tree, then commit.
            rendered_root = Path(LOCAL_GITOPS_FOLDER)
            push_root = rendered_root / ".push_tmp"
            if push_root.exists():
                shutil.rmtree(push_root)

            # Ensure we have a real git history to base changes on
            prev_git_ssh = os.environ.get("GIT_SSH_COMMAND")
            os.environ["GIT_SSH_COMMAND"] = ssh_cmd
            try:
                repo = Repo.clone_from(path, push_root, branch="main")
            finally:
                if prev_git_ssh is None:
                    os.environ.pop("GIT_SSH_COMMAND", None)
                else:
                    os.environ["GIT_SSH_COMMAND"] = prev_git_ssh

            def _wipe_worktree_except_git(dst: Path):
                for name in os.listdir(dst):
                    if name == ".git":
                        continue
                    p = dst / name
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        try:
                            p.unlink()
                        except Exception:
                            pass

            def _copy_tree(src: Path, dst: Path):
                for root, dirs, files in os.walk(src):
                    rel = os.path.relpath(root, src)
                    if rel == ".git" or rel.startswith(".git" + os.sep):
                        continue
                    if rel.startswith(".push_tmp"):
                        continue
                    dst_root = dst if rel == "." else (dst / rel)
                    os.makedirs(dst_root, exist_ok=True)
                    for f in files:
                        if f == ".DS_Store":
                            continue
                        src_file = Path(root) / f
                        if ".git" in src_file.parts or ".push_tmp" in src_file.parts:
                            continue
                        shutil.copy2(src_file, dst_root / f)

            # Make the clone match the rendered output exactly (authoritative)
            _wipe_worktree_except_git(push_root)
            _copy_tree(rendered_root, push_root)

            with repo.git.custom_environment(GIT_SSH_COMMAND=ssh_cmd):
                repo.git.add(all=True)
                if repo.is_dirty(untracked_files=True):
                    author = Actor(name=git_user_name, email=git_user_email)
                    repo.index.commit("chore: update generated gitops", author=author, committer=author)

                # First try normal push to main (fast-forward). If blocked, fallback to PR flow.
                try:
                    repo.git.push("origin", "main")
                    return
                except GitCommandError as e:
                    stderr = e.stderr or ""
                    if "Protected branch update failed" not in stderr and "protected branch hook declined" not in stderr:
                        # Not a protection issue: rethrow
                        raise

                # Protected main: push a branch based on main and open PR.
                import datetime
                branch = "cgdevx/generated/" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
                logger.warning(
                    f"Protected branch prevents direct push to main; pushing to branch '{branch}' instead."
                )
                repo.git.push("origin", f"HEAD:refs/heads/{branch}")

                if git_provider == GitProviders.GitHub and git_access_token:
                    pr_number, merged = GitOpsTemplateManager._create_github_pr_and_try_merge(
                        remote_url=path,
                        head_branch=branch,
                        token=git_access_token,
                        title="chore(gitops): sync generated GitOps",
                        body="Automated GitOps sync generated by cgdevxcli.\n\n"
                             "This PR is created because branch protection blocked direct pushes to main.",
                    )
                    if merged:
                        logger.warning(f"GitOps updates auto-merged via PR #{pr_number}.")
                        return
                    raise GitCommandError(
                        "git push",
                        1,
                        "",
                        f"GitOps updates pushed to '{branch}' and PR #{pr_number} created, but could not be auto-merged. "
                        f"Merge it to update main."
                    )

                raise GitCommandError(
                    "git push",
                    1,
                    "",
                    f"GitOps updates pushed to '{branch}'. Create a PR to merge into main."
                )

        except GitError as e:
            raise e

    @staticmethod
    @trace()
    def build_repo_from_template(git_provider: GitProviders):
        temp_folder = LOCAL_GITOPS_FOLDER / ".tmp"

        os.makedirs(LOCAL_GITOPS_FOLDER, exist_ok=True)
        # workaround for local development mode, this should not happen in prod
        for root, dirs, files in os.walk(temp_folder):
            for name in files:
                if name.endswith(".DS_Store") or name.endswith(".terraform") \
                        or name.endswith(".github") or name.endswith(".idea"):
                    path = os.path.join(root, name)
                    if os.path.isfile(path):
                        os.remove(path)
                    if os.path.isdir(path):
                        os.rmdir(path)

        shutil.copytree(temp_folder / "platform" / "terraform", LOCAL_GITOPS_FOLDER / "terraform")
        shutil.copytree(temp_folder / "platform" / "gitops-pipelines", LOCAL_GITOPS_FOLDER / "gitops-pipelines")
        for src_file in Path(temp_folder / "platform").glob('*.*'):
            shutil.copy(src_file, LOCAL_GITOPS_FOLDER)

        # drop all non template readme files
        for root, dirs, files in os.walk(LOCAL_GITOPS_FOLDER):
            for name in files:
                if name.endswith(".md") and not name.startswith("tpl_"):
                    os.remove(os.path.join(root, name))

        # rename readme file templates
        for root, dirs, files in os.walk(LOCAL_GITOPS_FOLDER):
            for name in files:
                if name.startswith("tpl_") and name.endswith(".md"):
                    s = os.path.join(root, name)
                    os.rename(s, s.replace("tpl_", ""))

        shutil.rmtree(temp_folder)
        return

    @trace()
    def parametrise_tf(self, state: StateStore):
        self.__file_replace(state, LOCAL_TF_FOLDER)
        # Some generated repos may already contain hardcoded Terraform backends (no placeholders).
        # Make backend bucket selection idempotent by overwriting backend blocks based on current state.
        self.__rewrite_tf_backend_bucket(state, LOCAL_TF_FOLDER)
        # Some template revisions contain GitHub branch protection arguments not supported by the
        # pinned GitHub provider version. Patch generated Terraform to keep setup idempotent.
        self.__fix_github_branch_protection_schema(LOCAL_TF_FOLDER)

    @trace()
    def parametrise(self, state: StateStore):
        self.__file_replace(state, LOCAL_GITOPS_FOLDER)

    @staticmethod
    def __file_replace(state: StateStore, folder):
        try:
            for root, dirs, files in os.walk(folder):
                for name in files:
                    if name.endswith(".tf") or name.endswith(".yaml") or name.endswith(".yml") or name.endswith(".md"):
                        file_path = os.path.join(root, name)
                        with open(file_path, "r") as file:
                            data = file.read()
                            for k, v in state.fragments.items():
                                data = data.replace(k, v)
                            for k, v in state.parameters.items():
                                data = data.replace(k, v)
                        with open(file_path, "w") as file:
                            file.write(data)
        except Exception as e:
            raise Exception(f"Error while parametrizing file: {file_path}", e)

    @staticmethod
    def __rewrite_tf_backend_bucket(state: StateStore, tf_root: Path):
        """
        Ensure terraform backend blocks in terraform/*/*.tf always use the currently selected backend bucket.

        This is required because some repos may have backends hardcoded (no '# <TF_*_REMOTE_BACKEND>' placeholders),
        which would otherwise keep stale bucket names forever.
        """
        # Map service folder -> fragment key in state.fragments
        fragment_by_service = {
            "vcs": "# <TF_VCS_REMOTE_BACKEND>",
            "hosting_provider": "# <TF_HOSTING_REMOTE_BACKEND>",
            "secrets": "# <TF_SECRETS_REMOTE_BACKEND>",
            "users": "# <TF_USERS_REMOTE_BACKEND>",
            "core_services": "# <TF_CORE_SERVICES_REMOTE_BACKEND>",
        }

        for service_dir in tf_root.iterdir():
            if not service_dir.is_dir():
                continue
            service = service_dir.name
            fragment_key = fragment_by_service.get(service)
            if not fragment_key:
                continue
            replacement = state.fragments.get(fragment_key)
            if not replacement:
                continue
            # Try to extract bucket name from the backend fragment
            bucket = None
            for line in replacement.splitlines():
                s = line.strip()
                if s.startswith("bucket"):
                    # bucket = "name"
                    parts = s.split("=", 1)
                    if len(parts) == 2:
                        val = parts[1].strip().strip('"')
                        if val:
                            bucket = val
                            break
            if not bucket:
                continue

            for tf_file in service_dir.rglob("*.tf"):
                try:
                    raw = tf_file.read_text()
                except Exception:
                    continue

                lines = raw.splitlines()
                updated_lines = []
                in_s3_backend = False
                backend_brace_depth = 0
                found_bucket_line = False

                for line in lines:
                    stripped = line.strip()

                    if not in_s3_backend and stripped.startswith('backend "s3"'):
                        in_s3_backend = True
                        backend_brace_depth = 0
                        found_bucket_line = False
                        updated_lines.append(line)
                        # Count braces on this line
                        backend_brace_depth += line.count("{") - line.count("}")
                        continue

                    if in_s3_backend:
                        backend_brace_depth += line.count("{") - line.count("}")

                        if stripped.startswith("bucket") and "=" in stripped:
                            indent = line[: len(line) - len(line.lstrip())]
                            updated_lines.append(f'{indent}bucket = "{bucket}"')
                            found_bucket_line = True
                        else:
                            # Before closing brace, inject bucket if missing
                            if backend_brace_depth <= 0 and stripped.startswith("}"):
                                if not found_bucket_line:
                                    indent = line[: len(line) - len(line.lstrip())]
                                    updated_lines.insert(len(updated_lines), f'{indent}  bucket = "{bucket}"')
                                    found_bucket_line = True
                                updated_lines.append(line)
                                in_s3_backend = False
                                backend_brace_depth = 0
                            else:
                                updated_lines.append(line)
                        continue

                    updated_lines.append(line)

                updated = "\n".join(updated_lines) + ("\n" if raw.endswith("\n") else "")
                if updated != raw:
                    try:
                        tf_file.write_text(updated)
                    except Exception:
                        continue

    @staticmethod
    def __fix_github_branch_protection_schema(tf_root: Path):
        """
        Ensure generated GitHub branch protection configuration is compatible with the pinned provider.

        If templates contain `push_restrictions = var.push_restrictions`, rewrite it to
        `restrict_pushes { push_allowances = var.push_restrictions }` and ensure the variable exists.
        """
        repo_tf = tf_root / "modules" / "vcs_github" / "repository" / "main.tf"
        repo_vars = tf_root / "modules" / "vcs_github" / "repository" / "variable.tf"

        if repo_tf.exists():
            try:
                data = repo_tf.read_text()
            except Exception:
                data = None

            if data and "push_restrictions" in data:
                # Remove direct argument line if present
                data = data.replace("  push_restrictions    = var.push_restrictions\n", "")

                # Add restrict_pushes block if not already present
                if "restrict_pushes" not in data:
                    anchor = "  force_push_bypassers = var.force_push_bypassers\n"
                    block = (
                        "  force_push_bypassers = var.force_push_bypassers\n"
                        "\n"
                        "  dynamic \"restrict_pushes\" {\n"
                        "    for_each = length(var.push_restrictions) > 0 ? [true] : []\n"
                        "    content {\n"
                        "      push_allowances = var.push_restrictions\n"
                        "    }\n"
                        "  }\n"
                    )
                    if anchor in data:
                        data = data.replace(anchor, block)

                try:
                    repo_tf.write_text(data)
                except Exception:
                    pass

        if repo_vars.exists():
            try:
                vdata = repo_vars.read_text()
            except Exception:
                vdata = None

            if vdata and "variable \"push_restrictions\"" not in vdata:
                vdata = vdata.rstrip() + "\n\n" + (
                    "variable \"push_restrictions\" {\n"
                    "  description = \"Optional: restrict who can push (GitHub branch protection restrict_pushes.push_allowances). Use '/username' or 'org/team' or node_id. Empty means no restriction.\"\n"
                    "  type        = list(string)\n"
                    "  default     = []\n"
                    "}\n"
                )
                try:
                    repo_vars.write_text(vdata)
                except Exception:
                    pass


class ProgressPrinter(RemoteProgress):
    @trace()
    def update(self, op_code, cur_count, max_count=None, message=""):
        # TODO: forward to CLI progress bar
        pass
