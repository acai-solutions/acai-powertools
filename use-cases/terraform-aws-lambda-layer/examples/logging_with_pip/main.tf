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
data "aws_region" "current" {
  provider = aws.workload
}


# ---------------------------------------------------------------------------------------------------------------------
# ¦ LOCALS
# ---------------------------------------------------------------------------------------------------------------------
locals {
  layer_settings = {
    layer_name               = "acai-powertools-logging-with-pip"
    description              = "ACAI logging module bundled with pip packages (requests)"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["logging"]
    pip_requirements = [
      "aws-lambda-powertools==2.43.1",
      "requests==2.32.3",
    ]
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

module "use_case_logging_with_pip_lambda" {
  #checkov:skip=CKV_TF_1: "Using a specific version from the public registry is generally safe, but always review the code and ensure it meets your security standards."
  source = "git::https://github.com/acai-solutions/terraform-aws-lambda?ref=1.5.2"

  lambda_settings = {
    function_name = "acai_powertools_logging_with_pip_test"
    description   = "Lambda using ACAI logging + pip requests library to call an external API"
    handler       = "main.lambda_handler"
    layer_arn_list = [
      module.acai_powertools_lambda_layer.layer_arn,
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
  depends_on      = [module.use_case_logging_with_pip_lambda]
  create_duration = "15s"
}

data "aws_lambda_invocation" "invoke_test_lambda" {
  function_name = module.use_case_logging_with_pip_lambda.lambda.name
  input         = jsonencode({ test = "terraform" })
  depends_on    = [time_sleep.wait_for_lambda]
  provider      = aws.workload
}

