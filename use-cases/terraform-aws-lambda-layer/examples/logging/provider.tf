# ---------------------------------------------------------------------------------------------------------------------
# ¦ PROVIDER
# ---------------------------------------------------------------------------------------------------------------------
provider "aws" {
  region = var.aws_region
  alias  = "workload"

  dynamic "assume_role" {
    for_each = var.iam_role_name != "" ? [1] : []
    content {
      role_arn = "arn:${var.aws_partition}:iam::${var.account_ids.workload}:role/${var.iam_role_name}"
    }
  }
}
