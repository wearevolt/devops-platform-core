# cgdevxcli setup hardening (Dec 2025)

This document captures the changes implemented during a troubleshooting session where `cgdevxcli setup` did not complete reliably (Vault init issues, ArgoCD sync failures, Terraform apply failures, and non-idempotent GitOps repo propagation).

It is written to answer:

- Why “old code” appeared in the generated GitOps repo (`pjc-platform`).
- What we changed to make template → generated GitOps repo propagation **idempotent** and robust.
- What we changed to make Vault init/unseal **idempotent**.
- What we changed to fix ArgoCD **repo authentication** (`ComparisonError`) and Terraform **branch protection schema** errors.

## Scope / Repos

All code changes referenced here were made in **`cg-devx-core`** and pushed to its remote `main`.

The GitOps repository being generated/updated by the CLI during setup is **`pjc-platform`**.

## High-level root causes

### 1) “Vault not installing” was a symptom, not the root problem

The setup pipeline was blocked earlier than Vault init:

- The CLI was waiting for `cert-manager` `Certificate` objects (e.g. `Certificate/vault-tls`) even though **cert-manager was not installed/used** in the cluster.
- Because the CLI got stuck, it never proceeded to create downstream resources like the `ConfigMap/vault-init`, which caused later Jobs to fail/stall.

### 2) “Old code deployed” was caused by non-idempotent GitOps repo upload logic

We found multiple failure modes that made the generated GitOps repository drift from the template:

- “repo-prep” checkpoint prevented regeneration of the GitOps working tree, so template changes were not always applied.
- Pushes were failing due to **non-fast-forward** or **branch protection**, leaving the remote unchanged.
- PR creation failed when the generated branch had **no common history** with `main` (branch was “unborn” / unrelated).
- PR creation also failed due to an incorrect GitHub API `head` format.

Net result: ArgoCD kept deploying what was already in `pjc-platform/main` (i.e. “old code”), because the CLI could not reliably update that repo.

### 3) ArgoCD `ComparisonError` was a separate hard blocker

Even after fixing generation/upload, ArgoCD can still fail to fetch the repo if it cannot authenticate to GitHub over SSH:

- ArgoCD shows `ComparisonError` when it cannot fetch or compare the Git revision.
- This prevents reconciliation and keeps workloads stuck on old manifests.

## Changes made (by area)

## A) Setup flow: remove cert-manager dependency

**Goal**: `cgdevxcli setup` must not hang on cert-manager resources when cert-manager is absent.

**What we did**:

- Added a Kubernetes client helper to detect if a CRD exists.
- Used that check to guard cert-manager `Certificate` waits (Vault/Harbor/SonarQube) and ultimately removed those waits from the setup flow.

**Files**:

- `tools/cli/commands/setup.py`
- `tools/cli/services/k8s/k8s.py`

**Key behavior change**:

- If `certificates.cert-manager.io` CRD is not present, setup does **not** waste time retrying Certificate reads/waits.

## B) Vault: make initialization idempotent and safe to re-run

**Goal**: rerunning setup must not fail on `vault operator init` when Vault is already initialized.

**What we did**:

- If Vault is already initialized, the CLI now reads the existing Kubernetes Secret (`vault-unseal-secret`) and reuses the stored `root-token` instead of re-initializing Vault.
- Added a safer Secret helper that decodes multiple keys from a Secret (reduces brittle ad-hoc base64 handling).

**Files**:

- `tools/cli/commands/setup.py`
- `tools/cli/services/k8s/k8s.py`

## C) GitOps repo generation + upload: make it idempotent and resilient

**Goal**: template changes must always propagate to `pjc-platform` deterministically, even across repeated runs.

**What we did**:

- Ensured GitOps repo generation runs even if the `repo-prep` checkpoint exists (so reruns still rebuild from template).
- Ensured placeholder parametrisation and “gitops-vcs push” are safe to rerun (avoid “only parametrised once” drift).
- Reworked upload logic to avoid fragile “stash on unborn branch” behaviors.
- Implemented an idempotent push strategy:
  - Primary: push updates to `main` using `--force-with-lease` (safer than raw `--force`).
  - Fallback: if `main` is protected, push to a generated branch, open a PR, and attempt to auto-merge.
- Fixed PR creation:
  - Ensure the generated branch shares history with `main` by cloning remote `main` into a temp dir, overlaying generated content, committing, then pushing.
  - Fixed GitHub API `head` format to `OWNER:branch` to avoid 422 errors.

**Files**:

- `tools/cli/services/platform_template_manager.py`
- `tools/cli/commands/setup.py` (orchestration / checkpoint behavior)

## D) Terraform (GitHub provider): fix branch protection schema drift

**Problem**: Terraform apply failed with `Unsupported argument: push_restrictions`.

**What we did**:

- Replaced unsupported `push_restrictions = ...` usage with the supported block-based schema:
  - `restrict_pushes { push_allowances = [...] }`
- Ensured the corresponding variable exists in generated modules.
- Added a patcher in the template manager to fix branch protection schema in generated Terraform when necessary.

**Files**:

- `platform/terraform/modules/vcs_github/repository/main.tf`
- `platform/terraform/modules/vcs_github/repository/variable.tf`
- `tools/cli/services/platform_template_manager.py`

**Reference (up-to-date provider docs)**:

- Terraform Provider GitHub docs for `github_branch_protection` indicate `restrict_pushes { push_allowances = [...] }` (and do not support a top-level `push_restrictions` argument).

## E) ArgoCD Git repo auth: provision deploy key for GitOps repo

**Problem**: ArgoCD could not authenticate to GitHub over SSH → `ComparisonError` → no sync → “old code” still running.

**What we did**:

- Provisioned a GitHub repository deploy key for the GitOps repo via Terraform, using the bot SSH public key already managed by the CLI inputs (`var.vcs_bot_ssh_public_key`).

**Files**:

- `platform/terraform/modules/vcs_github/repository/main.tf`
- `platform/terraform/modules/vcs_github/gitops_repo.tf`

## F) Logging security: redact sensitive values in trace logs

**Problem**: GitHub token (and other secrets) could appear in debug logs when passed as positional args.

**What we did**:

- Improved the tracing decorator redaction logic to redact sensitive positional arguments as well as keyword args.

**File**:

- `tools/cli/common/tracing_decorator.py`

## Commits (from this session)

Recent commits that contain the bulk of the changes above:

- `538fa57` — vault init idempotency + GitOps repo deploy key for ArgoCD; improve GitOps upload
- `6a989be` — idempotent GitOps generation/upload (PR flow) + redact secrets; fix GitHub branch protection schema
- `52f01ea` — idempotent AWS endpoints/kubeconfig + allow bot force-push to GitOps `main`
- `7b94b3b` / `87f7315` — Terraform backend bucket rewrite / stale backend auto-resolve improvements
- `f981cf0` / `ad40c53` / `0b73445` — additional idempotency hardening around GitOps placeholder re-parametrisation and repeatable pushes

## Chat summary / timeline (what happened and what we fixed)

This section is the “narrative” view of the session, not just the end-state.

- **Symptom**: Vault “was not installing”.
  - **Reality**: setup was blocked earlier (cert-manager waits), so Vault init resources were never reached/created.
- **Observed**: `wait-vault-init-complete` Job stuck due to missing `ConfigMap/vault-init`.
  - **Fix**: unblock setup flow by removing/guarding cert-manager waits so the CLI progresses to create that ConfigMap.
- **Terraform failure**: `Unsupported argument: push_restrictions`.
  - **Fix**: migrated to supported schema (`restrict_pushes { push_allowances = [...] }`) per Terraform GitHub provider docs.
- **GitOps upload failures**:
  - **non-fast-forward** push rejection → remote not updated.
  - **branch protection** prevents pushing to `main`.
  - **PR creation 422** (“no history in common”) due to unrelated branch history.
  - **PR creation 422** due to incorrect `head` format.
  - **Fix**: reworked upload to be history-aware (clone remote `main`, overlay generated tree, commit), then push with `--force-with-lease` or PR fallback; fixed `head=OWNER:branch`.
- **Security issue**: sensitive values (GitHub token) appeared in debug logs.
  - **Fix**: enhanced trace redaction to also cover positional args.
- **Vault re-run issue**: `vault operator init` fails when Vault is already initialized.
  - **Fix**: made Vault init idempotent by reading `vault-unseal-secret` and reusing the stored root token.
- **Current state**: SonarQube still didn’t come up even after GitOps repo content was updated.
  - **Most likely causes to check**:
    - ArgoCD repo authentication (`ComparisonError`) blocks sync, leaving workloads stale.
    - Image pulls failing (e.g. DockerHub rate limits, missing pull secret, network egress) for SonarQube/Postgres.

## How to rerun safely

Use whichever checkpoint matches where you want to resume. A common rerun once VCS Terraform is fixed:

```bash
cd tools/cli
poetry run cgdevxcli setup -f ../parameters.yaml --from-checkpoint vcs-tf --verbosity DEBUG
```

Notes:

- If you want a fully clean run, remove `~/.cgdevx/state.yaml` (this resets checkpoints).
- After rerun, the GitOps repo (`pjc-platform`) should be updated and ArgoCD should stop showing `ComparisonError` once repo auth is correct.

## Verification checklist (post-rerun)

### GitOps propagation

- Confirm `pjc-platform/main` contains the expected generated manifests (especially the SonarQube values you expect).
- Confirm ArgoCD Applications are **Synced/Healthy** (no `ComparisonError`).

### SonarQube recovery

If SonarQube is still not coming up:

- Check whether the Postgres image can be pulled (DockerHub rate limiting / connectivity / pull secrets).
- Collect Pod events for `sonarqube` and `sonarqube-postgresql` and correlate with ArgoCD status.

## Security notes (important)

- **Deploy key permissions**: a deploy key can be configured with write access. This unblocks ArgoCD repo fetch/push workflows but increases blast radius if the key leaks.
  - Recommendation: use **separate keys**:
    - a **read-only** key for ArgoCD repo access
    - a **write** key for the automation that writes to `pjc-platform`
- **Token redaction**: we improved redaction in trace logs, but still recommend avoiding logging raw inputs, and keeping DEBUG logs off in shared CI logs.

## Performance / reliability improvements

- Skipping cert-manager waits when CRDs are missing avoids long retry loops and reduces setup time.
- Rebuilding GitOps repo contents even when checkpoints exist improves idempotency and reduces “mystery drift”.
- Overlaying generated content onto a clone of `main` ensures PRs always have a valid merge base (reduces GitHub API failures).

## Open follow-up

- `verify-k8s-recovers`: After rerun, validate SonarQube comes up and ArgoCD apps converge. If not, collect events/logs and address image pull/auth issues.



