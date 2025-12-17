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
}
