package test

import (
	"fmt"
	"os/exec"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

func TestAcaiPowertoolsLambdaLayerWithPip(t *testing.T) {
	t.Log("Ensuring Python dependencies are installed...")
	cmd := exec.Command("bash", "-c", "pip3 show boto3 || pip3 install boto3")
	err := cmd.Run()
	if err != nil {
		t.Fatalf("Failed to ensure boto3 is installed: %v", err)
	}

	t.Log("Starting ACAI Powertools Lambda Layer with pip packages test")

	terraformDir := "../../examples/logging_with_pip"
	stateKey := "terratest/terraform-aws-acai-powertools-layer-with-pip.tfstate"
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

	// Verify the Lambda invocation result contains the expected powertools version
	// (proves the pip-installed aws-lambda-powertools is loadable from the layer
	// and that the version pinned in requirements.txt is what was bundled)
	expectedPowertoolsVersion := "2.43.1"
	lambdaInvokeResult := terraform.Output(t, terraformOptions, "lambda_invoke_result")
	t.Logf("Lambda invocation result: %s", lambdaInvokeResult)

	assert.Contains(t, lambdaInvokeResult, "powertools_version",
		"lambda_invoke_result should contain powertools_version field")
	assert.Contains(t, lambdaInvokeResult, expectedPowertoolsVersion,
		fmt.Sprintf("lambda_invoke_result should contain aws-lambda-powertools version %s (pinned in requirements.txt)", expectedPowertoolsVersion))
	assert.Contains(t, lambdaInvokeResult, "/opt/python/aws_lambda_powertools",
		"powertools should be loaded from the Lambda layer (/opt/python/...)")
}
