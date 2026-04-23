# ---------------------------------------------------------------------------------------------------------------------
# ¦ REQUIREMENTS
# ---------------------------------------------------------------------------------------------------------------------
terraform {
  required_version = ">= 1.3.10"

  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = ">= 5.0"
      configuration_aliases = []
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.0"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.9"
    }
  }
}


# ---------------------------------------------------------------------------------------------------------------------
# ¦ DATA
# ---------------------------------------------------------------------------------------------------------------------
data "aws_region" "current" {
  provider = aws.org_mgmt
}


# ---------------------------------------------------------------------------------------------------------------------
# ¦ LOCALS
# ---------------------------------------------------------------------------------------------------------------------
locals {
  layer_settings = {
    layer_name               = "acai-powertools-organizations"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["aws_helper"]
    skip_destroy             = false # Allow cleanup in test/dev environments
  }
}


# ---------------------------------------------------------------------------------------------------------------------
# ¦ LAMBDA LAYER
# ---------------------------------------------------------------------------------------------------------------------
module "acai_powertools_lambda_layer" {
  source         = "../../"
  layer_settings = local.layer_settings
  providers = {
    aws = aws.org_mgmt
  }
}

# ---------------------------------------------------------------------------------------------------------------------
# ¦ LAMBDA CONSUMING LAYER
# ---------------------------------------------------------------------------------------------------------------------
data "aws_iam_policy_document" "organizations_read" {
  #checkov:skip=CKV_AWS_356: Organizations read-only actions do not support resource-level permissions
  provider = aws.org_mgmt
  statement {
    effect = "Allow"
    actions = [
      "organizations:DescribeOrganization",
      "organizations:ListAccounts",
      "organizations:ListAccountsForParent",
      "organizations:ListRoots",
      "organizations:ListOrganizationalUnitsForParent",
      "organizations:DescribeOrganizationalUnit",
      "organizations:ListChildren",
      "organizations:ListTagsForResource",
      "organizations:DescribeAccount",
    ]
    resources = ["*"]
  }
}

module "use_case_1_lambda" {
  #checkov:skip=CKV_TF_1: "Using a specific version from the public registry is generally safe, but always review the code and ensure it meets your security standards."
  source = "git::https://github.com/acai-solutions/terraform-aws-lambda?ref=1.5.2"

  lambda_settings = {
    function_name = "acai_powertools_organizations_test"
    description   = "This Lambda will list all accounts and OUs from AWS Organizations and return them as JSON"
    handler       = "main.lambda_handler"
    layer_arn_list = [
      module.acai_powertools_lambda_layer.layer_arn
    ]
    config = {
      runtime      = local.layer_settings.compatible_runtimes[0]
      architecture = local.layer_settings.compatible_architectures[0]
    }
    package = {
      source_path = "${path.module}/lambda-files"
    }
  }
  execution_iam_role_settings = {
    new_iam_role = {
      permission_policy_json_list = [data.aws_iam_policy_document.organizations_read.json]
    }
  }
  providers = {
    aws = aws.org_mgmt
  }
}

## ---------------------------------------------------------------------------------------------------------------------
# ¦ INVOKE LAMBDA FROM TERRAFORM
## ---------------------------------------------------------------------------------------------------------------------
resource "time_sleep" "wait_for_lambda" {
  depends_on      = [module.use_case_1_lambda]
  create_duration = "15s"
  triggers = {
    layer_arn = module.acai_powertools_lambda_layer.layer_arn
  }
}

data "aws_lambda_invocation" "invoke_test_lambda" {
  function_name = module.use_case_1_lambda.lambda.name
  input         = jsonencode({ test = "terraform" })
  depends_on    = [time_sleep.wait_for_lambda]
  provider      = aws.org_mgmt
}


## ---------------------------------------------------------------------------------------------------------------------
# ¦ FETCH LAMBDA LOGS FROM CLOUDWATCH
## ---------------------------------------------------------------------------------------------------------------------
resource "null_resource" "fetch_lambda_logs" {
  provisioner "local-exec" {
    interpreter = ["python3", "-c"]
    command     = <<-EOT
import subprocess
subprocess.check_call(["aws", "logs", "filter-log-events", "--region", "${var.aws_region}", "--log-group-name", "/aws/lambda/${module.use_case_1_lambda.lambda.name}", "--limit", "10"])
    EOT
  }
  triggers = {
    lambda_invoke = data.aws_lambda_invocation.invoke_test_lambda.result
  }
}
