package test

import (
	"os/exec"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

func TestAcaiPowertoolsLambdaLayerWithInline(t *testing.T) {
	t.Log("Ensuring Python dependencies are installed...")
	cmd := exec.Command("bash", "-c", "pip3 show boto3 || pip3 install boto3")
	err := cmd.Run()
	if err != nil {
		t.Fatalf("Failed to ensure boto3 is installed: %v", err)
	}

	t.Log("Starting ACAI Powertools Lambda Layer with inline files test")

	terraformDir := "../../examples/logging_with_inline"
	stateKey := "terratest/terraform-aws-acai-powertools-layer-with-inline.tfstate"
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

	// Assert that the layer ARN is present
	layerArn := outputClean(t, terraformOptions, "acai_powertools_layer_arn")
	assert.NotEmpty(t, layerArn, "Layer ARN should not be empty")
	t.Logf("Layer ARN: %s", layerArn)

	// Verify the Lambda invocation result confirms the inline-injected
	// helper module is loadable from the layer at /opt/python/acme/...
	lambdaInvokeResult := outputRawClean(t, terraformOptions, "lambda_invoke_result")
	t.Logf("Lambda invocation result: %s", lambdaInvokeResult)

	assert.Contains(t, lambdaInvokeResult, "factory_module_path",
		"lambda_invoke_result should contain factory_module_path field")
	assert.Contains(t, lambdaInvokeResult, "/opt/python/acme/logging_factory.py",
		"inline helper should be loaded from the Lambda layer (/opt/python/acme/...)")
}
