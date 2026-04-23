package test

import (
	"encoding/json"
	"os"
	"testing"
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
