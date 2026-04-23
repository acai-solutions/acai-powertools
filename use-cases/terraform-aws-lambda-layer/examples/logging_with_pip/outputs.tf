output "acai_powertools_module" {
  value = module.acai_powertools_lambda_layer
}

output "acai_powertools_layer_arn" {
  value = module.acai_powertools_lambda_layer.layer_arn
}

output "lambda_invoke_result" {
  value = data.aws_lambda_invocation.invoke_test_lambda.result
}
