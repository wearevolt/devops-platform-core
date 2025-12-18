module "gitops-repo" {
  source = "./repository"

  repo_name                    = var.gitops_repo_name
  archive_on_destroy           = false
  # Keep branch protection enabled, but allow ONLY the bot to force-push to main
  # so the CLI can keep generated GitOps state up-to-date.
  allows_force_pushes  = true
  force_push_bypassers = var.vcs_bot_username != "" ? ["/${var.vcs_bot_username}"] : []
  atlantis_enabled             = true
  atlantis_url                 = var.atlantis_url
  atlantis_repo_webhook_secret = var.atlantis_repo_webhook_secret
  cd_webhook_url               = var.cd_webhook_url
  cd_webhook_secret            = var.cd_webhook_secret
  vcs_subscription_plan        = var.vcs_subscription_plan

  # ArgoCD fetches GitOps repo over SSH; attach the same public key as a deploy key to guarantee access.
  # NOTE: for best security, this should be a dedicated read-only key, but we reuse the bot key for now.
  deploy_key_public_key = var.vcs_bot_ssh_public_key
  deploy_key_read_only  = false
}
