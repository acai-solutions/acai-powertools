package test

import (
	"os/exec"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

func TestAcaiPowertoolsLambdaLayer(t *testing.T) {
	t.Log("Ensuring Python dependencies are installed...")
	cmd := exec.Command("bash", "-c", "pip3 show boto3 || pip3 install boto3")
	err := cmd.Run()
	if err != nil {
		t.Fatalf("Failed to ensure boto3 is installed: %v", err)
	}

	t.Log("Starting ACAI Powertools Lambda Layer test")

	terraformDir := "../../examples/logging"
	stateKey := uniqueStateKey("terratest/terraform-aws-acai-powertools-layer.tfstate")
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

	// Verify lambda_invoke_result matches fetch_lambda_logs_trigger
	lambdaInvokeResult := outputClean(t, terraformOptions, "lambda_invoke_result")
	fetchLambdaLogsTrigger := outputMapClean(t, terraformOptions, "fetch_lambda_logs_trigger")
	assert.Equal(t, lambdaInvokeResult, fetchLambdaLogsTrigger["lambda_invoke"],
		"lambda_invoke_result should equal fetch_lambda_logs_trigger[\"lambda_invoke\"]")
}
