# ---------------------------------------------------------------------------------------------------------------------
# ¦ BACKEND
# ---------------------------------------------------------------------------------------------------------------------
# Backend configuration is provided via partial configuration (-backend-config)
# by Terratest (backend.json) or CLI arguments.
terraform {
  backend "s3" {}
}
