# ---------------------------------------------------------------------------------------------------------------------
# ¦ PROVIDER
# ---------------------------------------------------------------------------------------------------------------------
provider "aws" {
  region = var.aws_region
  alias  = "org_mgmt"
}

provider "aws" {
  region = var.aws_region
  alias  = "core_logging"
  assume_role {
    role_arn = "arn:${var.aws_partition}:iam::${var.account_ids.core_logging}:role/${var.iam_role_name}"
  }
}

provider "aws" {
  region = var.aws_region
  alias  = "core_security"
  assume_role {
    role_arn = "arn:${var.aws_partition}:iam::${var.account_ids.core_security}:role/${var.iam_role_name}"
  }
}

provider "aws" {
  region = var.aws_region
  alias  = "core_backup"
  assume_role {
    role_arn = "arn:${var.aws_partition}:iam::${var.account_ids.core_backup}:role/${var.iam_role_name}"
  }
}

provider "aws" {
  region = var.aws_region
  alias  = "workload"
  assume_role {
    role_arn = "arn:${var.aws_partition}:iam::${var.account_ids.workload}:role/${var.iam_role_name}"
  }
}
