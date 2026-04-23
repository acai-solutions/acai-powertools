variable "layer_settings" {
  description = "HCL map of the Lambda-Layer-Settings."
  type = object({
    layer_name               = string
    description              = optional(string)
    compatible_runtimes      = list(string)
    compatible_architectures = list(string)
    acai_modules = optional(list(string), [
      "aws_helper",
      "logging",
      "python_helper",
      "storage"
    ])
    pip_requirements = optional(list(string), [])
    inline_files     = optional(map(string), {})
    skip_destroy     = optional(bool, false)
  })

  validation {
    condition = alltrue([
      for m in var.layer_settings.acai_modules : contains([
        "ai_embedding", "ai_hybrid_search", "ai_llm", "ai_text_search",
        "ai_tools", "ai_vector_store", "aws_helper", "logging",
        "python_helper", "storage", "webcrawler", "xml_parser"
      ], m)
    ])
    error_message = "Each module must be one of: ai_embedding, ai_hybrid_search, ai_llm, ai_text_search, ai_tools, ai_vector_store, aws_helper, logging, python_helper, storage, webcrawler, xml_parser."
  }

  validation {
    condition     = length(var.layer_settings.layer_name) > 0 && length(var.layer_settings.layer_name) <= 64
    error_message = "layer_name must be between 1 and 64 characters."
  }

  validation {
    condition     = length(var.layer_settings.compatible_runtimes) > 0
    error_message = "At least one compatible runtime must be specified."
  }

  validation {
    condition     = length(var.layer_settings.compatible_architectures) > 0
    error_message = "At least one compatible architecture must be specified."
  }

  validation {
    condition = alltrue([
      for r in var.layer_settings.compatible_runtimes :
      can(regex("^python3\\.\\d+$", r))
    ])
    error_message = "compatible_runtimes entries must match 'python3.<minor>' (e.g. 'python3.12'). Other Lambda runtimes are not supported by this module."
  }

  validation {
    condition = alltrue([
      for a in var.layer_settings.compatible_architectures :
      contains(["arm64", "x86_64"], a)
    ])
    error_message = "compatible_architectures entries must be one of: arm64, x86_64."
  }

  validation {
    condition = alltrue([
      for p in var.layer_settings.pip_requirements : length(trimspace(p)) > 0
    ])
    error_message = "layer_settings.pip_requirements entries must be non-empty pip requirement specs (e.g., \"requests==2.32.3\"). Pass file contents via split(\"\\n\", trimspace(file(\"requirements.txt\\\")))))."
  }

  validation {
    condition = (
      length(var.layer_settings.pip_requirements) == 0
      || (length(var.layer_settings.compatible_runtimes) == 1 && length(var.layer_settings.compatible_architectures) == 1)
    )
    error_message = "When pip_requirements is set, compatible_runtimes and compatible_architectures must each contain exactly one entry. Pip wheels are ABI/architecture specific; multi-runtime or multi-arch layers built from a single wheel set will crash at import time on the mismatched runtime."
  }

  validation {
    condition = alltrue([
      for k, _ in var.layer_settings.inline_files :
      length(k) > 0
      && !startswith(k, "/")
      && !startswith(k, "\\")
      && !can(regex("^[A-Za-z]:", k))
      && !contains(split("/", replace(k, "\\", "/")), "..")
    ])
    error_message = "layer_settings.inline_files keys must be relative paths (no leading '/' or '\\', no '..' segments anywhere, no drive letters)."
  }
}

variable "regions" {
  description = "Optional list of AWS regions to publish the layer in. When empty, the layer is published once in the provider's default region (backward compatible). Requires AWS provider >= 6.0."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for r in var.regions : can(regex("^[a-z]{2,4}(-[a-z]+)+-\\d+$", r))
    ])
    error_message = "Each region must look like 'us-east-1', 'eu-west-1', 'eusc-de-east-1', etc."
  }
}

# ---------------------------------------------------------------------------------------------------------------------
# ¦ COMMON
# ---------------------------------------------------------------------------------------------------------------------
variable "ssm_parameter_prefix" {
  description = "Optional prefix for SSM parameter holding the module version."
  type        = string
  default     = ""
}

variable "resource_tags" {
  description = "A map of tags to assign to the resources in this module."
  type        = map(string)
  default     = {}
}
