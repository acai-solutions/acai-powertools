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
data "aws_caller_identity" "current" {
  provider = aws.workload
}


# ---------------------------------------------------------------------------------------------------------------------
# ¦ LOCALS
# ---------------------------------------------------------------------------------------------------------------------
locals {
  layer_settings = {
    layer_name               = "acai-powertools-logging"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["logging"]
  }
}


# ---------------------------------------------------------------------------------------------------------------------
# ¦ MODULE
# ---------------------------------------------------------------------------------------------------------------------
module "acai_powertools_lambda_layer" {
  source         = "../../"
  layer_settings = local.layer_settings
  providers = {
    aws = aws.workload
  }
}

module "use_case_1_lambda" {
  #checkov:skip=CKV_TF_1: "Using a specific version from the public registry is generally safe, but always review the code and ensure it meets your security standards."
  source = "git::https://github.com/acai-solutions/terraform-aws-lambda?ref=1.5.2"

  lambda_settings = {
    function_name = "acai_powertools_logging_test"
    description   = "This Lambda will list all CloudWatch LogGroups and IAM Roles and return them as JSON"
    handler       = "main.lambda_handler"
    layer_arn_list = [
      module.acai_powertools_lambda_layer.layer_arn
    ]
    config = {
      runtime      = local.layer_settings.compatible_runtimes[0]
      architecture = local.layer_settings.compatible_architectures[0]
    }
    environment_variables = {
      ACCOUNT_ID = data.aws_caller_identity.current.account_id
    }
    package = {
      source_path = "${path.module}/lambda-files"
    }
  }
  providers = {
    aws = aws.workload
  }
}

## ---------------------------------------------------------------------------------------------------------------------
# ¦ INVOKE LAMBDA FROM TERRAFORM
## ---------------------------------------------------------------------------------------------------------------------

resource "time_sleep" "wait_for_lambda" {
  depends_on      = [module.use_case_1_lambda]
  create_duration = "15s"
}

data "aws_lambda_invocation" "invoke_test_lambda" {
  function_name = module.use_case_1_lambda.lambda.name
  input         = jsonencode({ test = "terraform" })
  depends_on    = [time_sleep.wait_for_lambda]
  provider      = aws.workload
}


## ---------------------------------------------------------------------------------------------------------------------
# ¦ FETCH LAMBDA LOGS FROM CLOUDWATCH
## ---------------------------------------------------------------------------------------------------------------------
resource "null_resource" "fetch_lambda_logs" {
  provisioner "local-exec" {
    interpreter = ["python", "-c"]
    command     = <<-EOT
import json, os, subprocess
role_arn = "${var.iam_role_name != "" ? "arn:${var.aws_partition}:iam::${var.account_ids.workload}:role/${var.iam_role_name}" : ""}"
if role_arn:
    creds = json.loads(subprocess.check_output(["aws", "sts", "assume-role", "--role-arn", role_arn, "--role-session-name", "terraform-logs", "--output", "json"]))
    os.environ["AWS_ACCESS_KEY_ID"] = creds["Credentials"]["AccessKeyId"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = creds["Credentials"]["SecretAccessKey"]
    os.environ["AWS_SESSION_TOKEN"] = creds["Credentials"]["SessionToken"]
subprocess.check_call(["aws", "logs", "filter-log-events", "--region", "${var.aws_region}", "--log-group-name", "/aws/lambda/${module.use_case_1_lambda.lambda.name}", "--limit", "10"])
    EOT
  }
  triggers = {
    lambda_invoke = data.aws_lambda_invocation.invoke_test_lambda.result
  }
}

