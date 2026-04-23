output "acai_powertools_module" {
  value = module.acai_powertools_lambda_layer
}


output "acai_powertools_layer_arn" {
  value = module.acai_powertools_lambda_layer.layer_arn
}

output "lambda_invoke_id" {
  description = "ID of the terraform_data resource that invoked the test Lambda"
  value       = terraform_data.invoke_test_lambda.id
}

output "fetch_lambda_logs_trigger" {
  description = "Trigger value for fetch_lambda_logs (shows Lambda invocation result used for log filtering)"
  value       = null_resource.fetch_lambda_logs.triggers
}
