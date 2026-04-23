output "layer_arn" {
  value       = length(var.regions) > 0 ? null : aws_lambda_layer_version.acai_powertools_layer["__default__"].arn
  description = "ARN of the ACAI PowerTools Lambda layer (single-region mode). Null when var.regions is set — use layer_arns instead."
}

output "layer_arns" {
  value = {
    for k, l in aws_lambda_layer_version.acai_powertools_layer :
    (k == "__default__" ? l.region : k) => l.arn
  }
  description = "Map of region => layer ARN for every published layer version."
}

output "layer_version" {
  value       = length(var.regions) > 0 ? null : aws_lambda_layer_version.acai_powertools_layer["__default__"].version
  description = "Version number of the Lambda layer (single-region mode)."
}

output "layer_source_code_hash" {
  value       = local.layer_inputs_hash
  description = "Deterministic, input-derived hash used as `source_code_hash` on the layer version. Stable across rebuilds (does not depend on zip mtimes)."
}

output "layer_name" {
  value       = var.layer_settings.layer_name
  description = "Name of the Lambda layer"
}
