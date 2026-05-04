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
  # Discover every file under ./inline-files/ and inject it into the layer
  # under the same relative path (e.g. inline-files/acme/logging_factory.py
  # -> /opt/python/acme/logging_factory.py).
  inline_files_dir = "${path.module}/inline-files"
  inline_files = {
    for relative_path in fileset(local.inline_files_dir, "**/*") :
    relative_path => file("${local.inline_files_dir}/${relative_path}")
  }

  layer_settings = {
    layer_name               = "acai-powertools-logging-with-inline"
    description              = "ACAI logging module with an inline-injected helper file (acme/logging_factory.py)"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["logging"]
    inline_files             = local.inline_files
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

module "use_case_logging_with_inline_lambda" {
  #checkov:skip=CKV_TF_1: "Using a specific version from the public registry is generally safe, but always review the code and ensure it meets your security standards."
  source = "git::https://github.com/acai-solutions/terraform-aws-lambda?ref=1.5.2"

  lambda_settings = {
    function_name = "acai_powertools_logging_with_inline_test"
    description   = "Lambda using an inline-injected helper module from the layer"
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
  depends_on      = [module.use_case_logging_with_inline_lambda]
  create_duration = "15s"
}

data "aws_lambda_invocation" "invoke_test_lambda" {
  function_name = module.use_case_logging_with_inline_lambda.lambda.name
  input         = jsonencode({ test = "terraform" })
  depends_on    = [time_sleep.wait_for_lambda]
  provider      = aws.workload
}
