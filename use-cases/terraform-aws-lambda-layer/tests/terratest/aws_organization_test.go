package test

import (
	"os/exec"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

func TestAcaiPowertoolsOrganizationsHelper(t *testing.T) {
	t.Log("Ensuring Python dependencies are installed...")
	cmd := exec.Command("bash", "-c", "pip3 show boto3 || pip3 install boto3")
	err := cmd.Run()
	if err != nil {
		t.Fatalf("Failed to ensure boto3 is installed: %v", err)
	}

	t.Log("Starting ACAI Powertools Organizations Helper test")

	terraformDir := "../../examples/aws_organization"
	stateKey := "terratest/terraform-aws-acai-powertools-organizations.tfstate"
	backendConfig := loadBackendConfig(t, stateKey)

	terraformOptions := &terraform.Options{
		TerraformBinary: getHclBinary(),
		TerraformDir:    terraformDir,
		NoColor:         false,
		Lock:            true,
		BackendConfig:   backendConfig,
		Reconfigure:     true,
	}
	defer terraform.Destroy(t, terraformOptions)
	terraform.InitAndApply(t, terraformOptions)

	// Retrieve and validate the module output
	output := terraform.OutputMap(t, terraformOptions, "acai_powertools_module")

	// Assert that the layer ARN is present
	layerArn, ok := output["layer_arn"]
	assert.True(t, ok, "Expected layer_arn in output")
	assert.NotEmpty(t, layerArn, "Layer ARN should not be empty")
	t.Logf("Layer ARN: %s", layerArn)

	// Verify lambda_invoke_result matches fetch_lambda_logs_trigger
	lambdaInvokeResult := terraform.Output(t, terraformOptions, "lambda_invoke_result")
	fetchLambdaLogsTrigger := terraform.OutputMap(t, terraformOptions, "fetch_lambda_logs_trigger")
	assert.Equal(t, lambdaInvokeResult, fetchLambdaLogsTrigger["lambda_invoke"],
		"lambda_invoke_result should equal fetch_lambda_logs_trigger[\"lambda_invoke\"]")

	// Verify Lambda invocation returned organization data
	assert.NotEmpty(t, lambdaInvokeResult, "Lambda invocation result should not be empty")
	t.Logf("Lambda invocation result: %s", lambdaInvokeResult)
}
