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

	// Assert that the layer ARN is present
	layerArn := terraform.Output(t, terraformOptions, "acai_powertools_layer_arn")
	assert.NotEmpty(t, layerArn, "Layer ARN should not be empty")
	t.Logf("Layer ARN: %s", layerArn)

	// Verify lambda invocation succeeded (terraform_data provisioner would have
	// failed the apply if the Lambda returned an error)
	lambdaInvokeId := terraform.Output(t, terraformOptions, "lambda_invoke_id")
	assert.NotEmpty(t, lambdaInvokeId, "Lambda invoke ID should not be empty")
	t.Logf("Lambda invoke ID: %s", lambdaInvokeId)

	// Verify fetch_lambda_logs_trigger references the invocation
	fetchLambdaLogsTrigger := terraform.OutputMap(t, terraformOptions, "fetch_lambda_logs_trigger")
	assert.Equal(t, lambdaInvokeId, fetchLambdaLogsTrigger["lambda_invoke"],
		"lambda_invoke_id should equal fetch_lambda_logs_trigger[\"lambda_invoke\"]")
}
