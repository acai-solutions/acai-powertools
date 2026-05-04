# ---------------------------------------------------------------------------------------------------------------------
# ¦ REQUIREMENTS
# ---------------------------------------------------------------------------------------------------------------------
terraform {
  required_version = ">= 1.3.10"

  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = ">= 6.0"
      configuration_aliases = []
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.0"
    }
  }
}

# ---------------------------------------------------------------------------------------------------------------------
# ¦ MODULE VERSION
# ---------------------------------------------------------------------------------------------------------------------
locals {
  resource_tags = merge(
    var.resource_tags,
    {
      "product"       = "PowerTools",
      "semper_vendor" = "ACAI GmbH",
    }
  )
  aws_ssm_parameter_prefix = var.ssm_parameter_prefix == "" ? "" : "/${lower(var.ssm_parameter_prefix)}"
  solution_version         = /*inject_version_start*/ "1.0.7" /*inject_version_end*/
}
resource "aws_ssm_parameter" "product_version" {
  #checkov:skip=CKV2_AWS_34: AWS SSM Parameter should be Encrypted not required for module version
  # Note: this parameter is created in the provider's default region only,
  # even when var.regions is used to publish the layer in multiple regions.
  name           = "${local.aws_ssm_parameter_prefix}/acai/powertools/productversion"
  type           = "String"
  insecure_value = local.solution_version
  overwrite      = true
  tags           = local.resource_tags
}


# ---------------------------------------------------------------------------------------------------------------------
# ¦ LOCALS
# ---------------------------------------------------------------------------------------------------------------------
locals {
  # Per-instance build paths keyed by layer_name — keeps `for_each`
  # invocations from sharing (and racing on) the same directories/zip.
  # Build artefacts live under path.root (the consumer workspace) instead of
  # path.module (which lives inside .terraform/modules/ and gets wiped by
  # `terraform init` in CI apply stages).
  # IMPORTANT: abspath() is required because the provisioner runs with
  # working_dir = path.module, so relative paths would resolve against the
  # module directory, not the root module directory. The resource's `filename`
  # attribute, however, resolves relative to the root module. Using absolute
  # paths ensures both the build script and the resource reference the same file.
  layer_source_folder       = "${abspath(path.root)}/.layer-build/${var.layer_settings.layer_name}"
  zip_folder                = "${abspath(path.root)}/.layer-build"
  acai_powertools_layer_zip = "${local.zip_folder}/${var.layer_settings.layer_name}.zip"

  is_windows = length(regexall("^[A-Za-z]:[\\\\/]", abspath(path.module))) > 0

  has_acai_modules = length(var.layer_settings.acai_modules) > 0
  modules_arg      = local.has_acai_modules ? "--modules ${join(" ", var.layer_settings.acai_modules)} --resolve-deps" : "--no-acai"

  # Hash of the acai source tree so layer rebuilds when library code changes.
  acai_source_dir = "${path.module}/../../lib/acai"
  acai_source_hash = local.has_acai_modules ? sha1(join("", [
    for f in fileset(local.acai_source_dir, "**/*.py") :
    filesha1("${local.acai_source_dir}/${f}")
  ])) : ""

  # Derive pip target platform from compatible_architectures
  arch_platform_map = {
    "arm64"  = "manylinux2014_aarch64"
    "x86_64" = "manylinux2014_x86_64"
  }
  pip_platform          = try(local.arch_platform_map[var.layer_settings.compatible_architectures[0]], null)
  runtime_version_parts = try(regex("(\\d+)\\.(\\d+)", var.layer_settings.compatible_runtimes[0]), null)
  pip_python_version    = local.runtime_version_parts != null ? "${local.runtime_version_parts[0]}${local.runtime_version_parts[1]}" : null

  pip_requirements      = var.layer_settings.pip_requirements
  has_pip_requirements  = length(local.pip_requirements) > 0
  pip_requirements_json = local.has_pip_requirements ? jsonencode(local.pip_requirements) : ""
  pip_req_arg           = local.has_pip_requirements ? "--requirements" : ""
  pip_platform_arg      = local.has_pip_requirements && local.pip_platform != null ? "--pip-platform ${local.pip_platform}" : ""
  pip_version_arg       = local.has_pip_requirements && local.pip_python_version != null ? "--pip-python-version ${local.pip_python_version}" : ""
  pip_args              = trimspace("${local.pip_req_arg} ${local.pip_platform_arg} ${local.pip_version_arg}")
  pip_requirements_hash = local.has_pip_requirements ? md5(local.pip_requirements_json) : ""

  has_inline_files  = length(var.layer_settings.inline_files) > 0
  inline_files_json = local.has_inline_files ? jsonencode(var.layer_settings.inline_files) : ""
  inline_files_arg  = local.has_inline_files ? "--inline-files" : ""

  # Deterministic, input-based hash for the layer.
  # Used as `source_code_hash` so that `aws_lambda_layer_version` is only
  # replaced when the *inputs* change, not when the zip bytes happen to
  # differ (e.g. due to file mtimes embedded in the archive on a rebuild).
  # NOTE: compatible_runtimes / compatible_architectures are not included
  # here — they are first-class attributes of `aws_lambda_layer_version`
  # and already trigger a replacement on their own when changed.
  layer_inputs_hash = base64sha256(jsonencode({
    modules            = var.layer_settings.acai_modules
    acai_source        = local.acai_source_hash
    requirements       = local.pip_requirements_hash
    inline_files       = local.has_inline_files ? md5(local.inline_files_json) : ""
    pip_platform       = local.pip_platform
    pip_python_version = local.pip_python_version
  }))


  # Multi-region publishing: when var.regions is non-empty, publish a layer
  # version per region using the AWS provider v6 `region` resource argument.
  # When empty, publish a single layer version in the provider's default region
  regions_set = length(var.regions) > 0 ? toset(var.regions) : toset(["__default__"])
}

# ---------------------------------------------------------------------------------------------------------------------
# ¦ BUILD LAYER SOURCE + ZIP
# ---------------------------------------------------------------------------------------------------------------------
resource "null_resource" "build_layer" {
  # Rebuild when inputs change OR when the zip is missing on the current agent.
  # The zip path uses abspath(path.root) so it resolves identically in both
  # the provisioner (working_dir = path.module) and the resource's filename.
  triggers = {
    inputs_hash = local.layer_inputs_hash
    zip_present = fileexists(local.acai_powertools_layer_zip) ? "yes" : timestamp()
  }

  provisioner "local-exec" {
    interpreter = local.is_windows ? ["powershell", "-Command"] : ["/bin/sh", "-c"]
    command = local.is_windows ? trimspace(
      "python build_layer.py ${local.modules_arg} ${local.pip_args} ${local.inline_files_arg} --source-dir \"${local.layer_source_folder}\" --output \"${local.acai_powertools_layer_zip}\""
      ) : trimspace(
      "if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi && \"$PY\" build_layer.py ${local.modules_arg} ${local.pip_args} ${local.inline_files_arg} --source-dir '${local.layer_source_folder}' --output '${local.acai_powertools_layer_zip}'"
    )
    working_dir = path.module
    environment = {
      PIP_REQUIREMENTS_JSON = local.pip_requirements_json
      INLINE_FILES_JSON     = local.inline_files_json
    }
  }
}

# ---------------------------------------------------------------------------------------------------------------------
# ¦ LAMBDA LAYER (one per region — uses AWS provider v6 `region` argument)
# ---------------------------------------------------------------------------------------------------------------------
resource "aws_lambda_layer_version" "acai_powertools_layer" {
  for_each = local.regions_set

  region                   = each.key == "__default__" ? null : each.key
  layer_name               = var.layer_settings.layer_name
  description              = var.layer_settings.description
  filename                 = local.acai_powertools_layer_zip
  compatible_runtimes      = var.layer_settings.compatible_runtimes
  compatible_architectures = var.layer_settings.compatible_architectures
  source_code_hash         = local.layer_inputs_hash
  skip_destroy             = var.layer_settings.skip_destroy

  depends_on = [null_resource.build_layer]

  lifecycle {
    create_before_destroy = true
  }
}
