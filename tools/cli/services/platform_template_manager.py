import os
import pathlib
import shutil
import re
from pathlib import Path
from urllib.error import HTTPError

import requests
from ghrepo import GHRepo
from git import Repo, RemoteProgress, GitError, Actor

from common.const.common_path import LOCAL_TF_FOLDER, LOCAL_GITOPS_FOLDER
from common.const.const import GITOPS_REPOSITORY_URL, GITOPS_REPOSITORY_BRANCH
from common.enums.git_providers import GitProviders
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
    @trace()
    def upload(path: str, key_path: str, git_user_name: str, git_user_email: str):

        if not os.path.exists(LOCAL_GITOPS_FOLDER):
            raise Exception("GitOps repo does not exist")

        try:
            ssh_cmd = f'ssh -o StrictHostKeyChecking=no -i {key_path}'

            repo = Repo.init(LOCAL_GITOPS_FOLDER, **{"initial-branch": "main"})

            with repo.git.custom_environment(GIT_SSH_COMMAND=ssh_cmd):
                # ensure we have origin
                if not any(repo.remotes):
                    repo.create_remote(name='origin', url=path)
                elif "origin" not in [r.name for r in repo.remotes]:
                    repo.create_remote(name='origin', url=path)

                # always keep branch name stable
                repo.git.checkout("-B", "main")

                # commit only when there are changes
                repo.git.add(all=True)
                if repo.is_dirty(untracked_files=True):
                    author = Actor(name=git_user_name, email=git_user_email)
                    repo.index.commit("chore: update generated gitops", author=author, committer=author)

                # force-with-lease so the remote reflects current generated state (idempotent re-runs)
                repo.git.push("--force-with-lease", "origin", "main")

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
        self.__rewrite_tf_backends(state, LOCAL_TF_FOLDER)

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
    def __rewrite_tf_backends(state: StateStore, tf_root: Path):
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

        backend_re = re.compile(r'(?:^|\n)(?P<indent>[ \t]*)backend\s+"s3"\s*\{[\s\S]*?\n(?P=indent)\}', re.MULTILINE)

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

            for tf_file in service_dir.rglob("*.tf"):
                try:
                    raw = tf_file.read_text()
                except Exception:
                    continue

                m = backend_re.search(raw)
                if not m:
                    continue

                indent = m.group("indent") or ""
                # Indent replacement to match existing backend indentation
                repl_lines = []
                for i, line in enumerate(replacement.splitlines()):
                    if i == 0:
                        repl_lines.append(f"{indent}{line.rstrip()}")
                    else:
                        repl_lines.append(f"{indent}{line.rstrip()}" if line.strip() else line)
                repl = "\n" + "\n".join(repl_lines)

                updated = backend_re.sub(repl, raw, count=1)
                if updated != raw:
                    try:
                        tf_file.write_text(updated)
                    except Exception:
                        continue


class ProgressPrinter(RemoteProgress):
    @trace()
    def update(self, op_code, cur_count, max_count=None, message=""):
        # TODO: forward to CLI progress bar
        pass
