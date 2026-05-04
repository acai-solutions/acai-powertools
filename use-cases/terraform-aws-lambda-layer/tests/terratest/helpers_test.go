package test

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
)

func loadBackendConfig(t *testing.T, stateKey string) map[string]interface{} {
	backendConfig := map[string]interface{}{}
	data, err := os.ReadFile("backend.json")
	if err != nil {
		t.Logf("No backend.json found, using local state: %v", err)
		return nil
	}
	if err := json.Unmarshal(data, &backendConfig); err != nil {
		t.Fatalf("Failed to parse backend.json: %v", err)
	}
	if stateKey != "" {
		backendConfig["key"] = stateKey
	}
	return backendConfig
}

func getHclBinary() string {
	if bin := os.Getenv("TERRATEST_TERRAFORM_BINARY"); bin != "" {
		return bin
	}
	return "terraform"
}

// outputClean runs "terraform output -json <key>" and strips any trailing
// Terraform warnings before JSON-unmarshalling the result into a string.
// This works around deprecated-backend-parameter warnings polluting stdout.
func outputClean(t *testing.T, options *terraform.Options, key string) string {
	t.Helper()
	args := []string{"output", "-no-color", "-json", key}
	stdout, err := terraform.RunTerraformCommandAndGetStdoutE(t, options, args...)
	if err != nil {
		t.Fatalf("Failed running terraform output for %q: %v", key, err)
	}
	// Trim everything after the first newline that starts a warning block
	if idx := strings.Index(stdout, "\nWarning:"); idx != -1 {
		stdout = stdout[:idx]
	}
	stdout = strings.TrimSpace(stdout)
	var value string
	if err := json.Unmarshal([]byte(stdout), &value); err != nil {
		t.Fatalf("Failed to parse terraform output %q: %v\nRaw output: %s", key, err, stdout)
	}
	return value
}

// outputMapClean runs "terraform output -json <key>" and strips trailing
// warnings before unmarshalling into map[string]string.
func outputMapClean(t *testing.T, options *terraform.Options, key string) map[string]string {
	t.Helper()
	args := []string{"output", "-no-color", "-json", key}
	stdout, err := terraform.RunTerraformCommandAndGetStdoutE(t, options, args...)
	if err != nil {
		t.Fatalf("Failed running terraform output for %q: %v", key, err)
	}
	if idx := strings.Index(stdout, "\nWarning:"); idx != -1 {
		stdout = stdout[:idx]
	}
	stdout = strings.TrimSpace(stdout)
	var value map[string]string
	if err := json.Unmarshal([]byte(stdout), &value); err != nil {
		t.Fatalf("Failed to parse terraform output map %q: %v\nRaw output: %s", key, err, stdout)
	}
	return value
}

// outputRawClean runs "terraform output -json <key>" and strips trailing
// warnings, returning the trimmed raw JSON string for manual inspection.
func outputRawClean(t *testing.T, options *terraform.Options, key string) string {
	t.Helper()
	args := []string{"output", "-no-color", "-json", key}
	stdout, err := terraform.RunTerraformCommandAndGetStdoutE(t, options, args...)
	if err != nil {
		t.Fatal(fmt.Errorf("terraform output %q: %w", key, err))
	}
	if idx := strings.Index(stdout, "\nWarning:"); idx != -1 {
		stdout = stdout[:idx]
	}
	return strings.TrimSpace(stdout)
}
