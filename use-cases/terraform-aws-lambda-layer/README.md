# AWS Lambda Layer Module - ACAI PowerTools

A production-grade Terraform module that builds and deploys AWS Lambda layers containing ACAI PowerTools Python modules with intelligent dependency resolution.

## Features

- 🔧 **Modular Design**: Select and combine only the ACAI modules you need
- 📦 **Dependency Resolution**: Automatically resolves and includes transitive dependencies
- � **Pip Packages**: Bundle third-party libraries from a `requirements.txt` (cross-compiled to the right manylinux wheels — no Docker required)
- 📝 **Inline Files**: Bake your own Python files / packages directly into the layer from HCL or from a folder
- �🔐 **Layer Protection**: Built-in lifecycle management prevents accidental deletion
- 🎯 **Architecture Aware**: Supports multiple runtimes and processor architectures
- ✅ **Validated**: Input validation ensures only known modules are included
- 🚀 **Terraform Native**: Pure Terraform with no external dependencies beyond Python

## Available Modules

The following ACAI PowerTools modules can be included:

| Module | Dependencies | Purpose |
|--------|--------------|---------|
| `ai_embedding` | `logging` | AI embedding functionality |
| `ai_hybrid_search` | `logging` | Hybrid search capabilities |
| `ai_llm` | `logging` | Large Language Model integrations |
| `ai_text_search` | `logging` | Text search functionality |
| `ai_tools` | None | AI utility tools |
| `ai_vector_store` | `logging` | Vector store operations |
| `aws_helper` | `logging` | AWS boto3 helpers |
| `logging` | `storage` | Logging utilities |
| `python_helper` | None | Python utility functions |
| `storage` | `logging` | Storage operations |
| `webcrawler` | `logging` | Web crawling utilities |
| `xml_parser` | `logging` | XML parsing utilities |

## Usage

### Basic Example

```hcl
module "acai_powertools_layer" {
  source = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=1.0.0"

  layer_settings = {
    layer_name               = "acai-powertools-basic"
    description              = "ACAI PowerTools with logging and boto3"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["logging", "aws_helper"]
  }
}
```

### With Automatic Dependency Resolution

```hcl
module "acai_powertools_layer" {
  source = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=v1.0.0"

  layer_settings = {
    layer_name               = "acai-powertools-ai"
    description              = "ACAI PowerTools with AI modules"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["x86_64", "arm64"]
    acai_modules             = ["ai_llm", "ai_embedding"]
    # Dependencies will be auto-resolved: logging and storage will be included
  }
}
```

### With pip Packages (requirements.txt)

Bundle third-party pip packages alongside ACAI modules. The target platform is
auto-derived from `compatible_architectures` / `compatible_runtimes`, so packages
with native C extensions get the correct manylinux wheels — no Docker required.

```hcl
module "acai_powertools_layer" {
  source = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=v1.0.0"

  layer_settings = {
    layer_name               = "acai-powertools-full"
    description              = "ACAI PowerTools with extra pip packages"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["logging", "aws_helper"]
    pip_requirements = [
      "aws-lambda-powertools==2.43.1",
      "requests==2.32.3",
    ]
  }
}
```

`pip_requirements` is a list of **pip requirement spec strings** — i.e. the
lines you would otherwise put in `requirements.txt`. To reuse an existing
file on disk, splat it in:

```hcl
pip_requirements = compact(split("\n", trimspace(file("${path.module}/requirements.txt"))))
```

### pip-Only Layer (no ACAI modules)

Set `acai_modules = []` to create a layer that contains only pip packages:

```hcl
module "libraries_layer" {
  source = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=v1.0.0"

  layer_settings = {
    layer_name               = "python-libraries"
    description              = "Third-party Python libraries"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = []
    pip_requirements = [
      "boto3>=1.34",
      "requests==2.32.3",
    ]
  }
}
```

### With Inline Files (bake your own modules into the layer)

Use `inline_files` to inject arbitrary Python files (or other text assets) into
the layer's `python/` directory. Keys are **relative paths** (no leading `/`,
no `..`, no drive letters); values are the file contents. Missing `__init__.py`
files are auto-created so new package directories are importable out of the box.

Files end up at `/opt/python/<your-relative-path>` inside the Lambda runtime,
so the example below makes `from acme.logging_factory import setup_logging`
available to every function that attaches the layer.

#### Inline content directly in HCL

```hcl
module "acai_powertools_layer" {
  source = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=v1.0.0"

  layer_settings = {
    layer_name               = "acai-powertools-with-inline"
    description              = "ACAI logging + an inline-injected helper module"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["logging"]
    inline_files = {
      "acme/logging_factory.py" = <<-EOT
        import os
        from acai.logging import create_lambda_logger
        from acai.logging.domain import LoggerConfig

        def setup_logging(service_name, log_level=None):
            return create_lambda_logger(LoggerConfig(
                service_name=service_name,
                log_level=log_level or os.getenv("LOG_LEVEL", "INFO").upper(),
            ))
      EOT
    }
  }
}
```

#### Inline content from a folder (recommended for non-trivial code)

Keep the payload as real `.py` files on disk and let Terraform discover them —
drop in any new file under `inline-files/` and it gets baked into the next
build at the same relative path:

```hcl
locals {
  inline_files_dir = "${path.module}/inline-files"
  inline_files = {
    for relative_path in fileset(local.inline_files_dir, "**/*") :
    relative_path => file("${local.inline_files_dir}/${relative_path}")
  }

  layer_settings = {
    layer_name               = "acai-powertools-with-inline"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["logging"]
    inline_files             = local.inline_files
  }
}

module "acai_powertools_layer" {
  source         = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=v1.0.0"
  layer_settings = local.layer_settings
}
```

Folder layout:
```
your-stack/
├── main.tf
└── inline-files/
    └── acme/
        └── logging_factory.py    # → /opt/python/acme/logging_factory.py
```

`inline_files`, `pip_requirements`, and `acai_modules` can be combined freely —
all three end up side-by-side in the same layer.

### Using the Layer in Lambda Functions

```hcl
resource "aws_lambda_function" "my_function" {
  filename      = "lambda.zip"
  function_name = "my-acai-function"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.12"
  architectures = ["arm64"]

  layers = [module.acai_powertools_layer.layer_arn]
}
```

### Multi-Layer Setup

```hcl
module "acai_logging_layer" {
  source = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=v1.0.0"

  layer_settings = {
    layer_name               = "acai-logging"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["logging"]
  }
}

module "acai_ai_layer" {
  source = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=v1.0.0"

  layer_settings = {
    layer_name               = "acai-ai"
    compatible_runtimes      = ["python3.12"]
    compatible_architectures = ["arm64"]
    acai_modules             = ["ai_llm", "ai_embedding"]
  }
}

resource "aws_lambda_function" "my_function" {
  # ... other config ...
  layers = [
    module.acai_logging_layer.layer_arn,
    module.acai_ai_layer.layer_arn
  ]
}
```

## Inputs

### `layer_settings` (Required)

Object containing Lambda layer configuration:

```hcl
layer_settings = {
  layer_name               = string           # Name of the Lambda layer
  description              = string           # (Optional) Layer description
  compatible_runtimes      = list(string)     # e.g., ["python3.12"]
  compatible_architectures = list(string)     # e.g., ["arm64", "x86_64"]
  acai_modules             = list(string)     # Modules to include (see Available Modules table)
  pip_requirements         = list(string)     # (Optional) pip requirement spec lines (e.g. "requests==2.32.3")
  inline_files             = map(string)      # (Optional) "relative/path" => file content
  skip_destroy             = bool             # (Optional, default false) keep layer version on destroy when true
}
```

**Validation:**
- `layer_name`: Required, max 64 characters
- `description`: Optional, recommended for clarity
- `compatible_runtimes`: Required, must be valid Python runtimes (e.g., "python3.12")
- `compatible_architectures`: Required, e.g., "arm64" or "x86_64"
- `acai_modules`: Optional, defaults to `["aws_helper", "logging", "python_helper", "storage"]`
  - Only known module names allowed
  - Dependencies are automatically resolved and included
- `pip_requirements`: Optional, defaults to `[]`. Each entry is a **pip
  requirement spec line** (the same syntax you would put in a
  `requirements.txt` — e.g. `"requests==2.32.3"` or `"boto3>=1.34"`). All
  entries are written to a single temporary requirements file and installed
  in one `pip install -r` invocation, so version pins resolve together. The
  target platform (`--platform manylinux2014_*`) and Python version are
  **auto-derived** from `compatible_architectures[0]` and
  `compatible_runtimes[0]`, so native wheels are fetched without Docker.
  To reuse an existing `requirements.txt` on disk, use
  `compact(split("\n", trimspace(file("requirements.txt"))))`.
- `inline_files`: Optional, defaults to `{}`. Map of `relative/path → file
  content` baked into the layer at `/opt/python/<key>`. Keys must be **relative**
  paths (no leading `/`, no `..`, no Windows drive letters). Missing
  `__init__.py` files are auto-generated for every new package directory.
- `skip_destroy`: Optional, defaults to `false`. Set to `true` only when you
  need to retain old layer versions across `terraform destroy` (e.g. shared
  production layers consumed by Lambdas outside this stack). Note: layer
  versions are immutable and AWS provides no bulk delete — leaving this on
  in CI/dev stacks will accumulate orphan versions in the account.

## Outputs

| Output | Description |
|--------|-------------|
| `layer_arn` | ARN of the created Lambda layer |
| `layer_version` | Version number of the Lambda layer |
| `layer_source_code_hash` | Base64-encoded SHA256 hash of the layer zip |
| `layer_name` | Name of the Lambda layer |

### Example Usage of Outputs

```hcl
output "my_layer_arn" {
  value       = module.acai_powertools_layer.layer_arn
  description = "ARN of the ACAI PowerTools layer"
}

output "layer_version" {
  value       = module.acai_powertools_layer.layer_version
  description = "Version number of the ACAI PowerTools layer"
}
```

## How It Works

1. **Module Collection**: The module uses `build_layer.py` to collect selected ACAI modules
2. **Dependency Resolution**: Dependencies are automatically resolved and included (unless deselected)
3. **ZIP Creation**: All selected modules are zipped into a Lambda layer structure
4. **Layer Deployment**: Terraform creates the Lambda layer with specified configurations
5. **Lifecycle Protection**: `skip_destroy = true` prevents accidental deletion in production

### Directory Structure

```
10-layer-source/          # Intermediate build directory
├── python/
│   ├── acai/             # ACAI modules
│   │   ├── logging/
│   │   ├── aws_helper/
│   │   └── ...
│   ├── requests/         # pip packages (when pip_requirements is set)
│   ├── urllib3/
│   └── acme/             # inline_files (when inline_files is set)
│       ├── __init__.py   #   ← auto-created
│       └── logging_factory.py
20-zipped/                # Output directory
└── acai_powertools_layer.zip
```

## Requirements

### Terraform
- Terraform >= 1.3.10
- AWS Provider >= 5.0
- `null` Provider >= 3.0
- `archive` Provider >= 2.0

### System Requirements
- Python 3.8+
- Write permissions in module directory (for build artifacts)

## Best Practices

### 1. Use Specific Module Versions
```hcl
module "acai_powertools_layer" {
  source = "git::https://github.com/acai-solutions/acai-powertools.git//use-cases/terraform-aws-lambda-layer?ref=v1.0.0"
  # Always pin to a specific version/tag
}
```

### 2. Separate Layers by Concern
Instead of single large layer with all modules:
```hcl
# Good: Separate concern
module "core_layer" {
  acai_modules = ["logging", "aws_helper"]
}

module "ai_layer" {
  acai_modules = ["ai_llm"]  # auto-resolves logging dependency
}
```

### 3. Document Your Module Selection
```hcl
layer_settings = {
  layer_name = "acai-core"
  description = "Core ACAI modules: logging, boto3 helpers, Python utilities"
  # ...
  acai_modules = ["logging", "aws_helper", "python_helper"]
}
```

### 4. Plan for Layer Updates
Keep track of layer versions when updating `acai_modules`:
```hcl
# Version changes when modules change (tracked via source_code_hash)
output "layer_update_detected" {
  value       = "Layer rebuilt due to module changes"
  depends_on  = [aws_lambda_layer_version.acai_powertools_layer]
}
```

### 5. Test in Development First
Use a development environment to test layer changes before production:
```hcl
# dev.tfvars
account_id = "111111111111"  # Dev account
layer_name_suffix = "-dev"

# prod.tfvars
account_id = "222222222222"  # Prod account
layer_name_suffix = "-prod"
```

## Troubleshooting

### Error: "Python 3.8+ is required"
Ensure Python 3.8 or later is installed and in your PATH:
```bash
python --version
```

### Error: "Module directory not found"
The module expects to find ACAI source code at `../lib/acai/`. Verify your repository structure:
```
your-repo/
├── lib/
│   └── acai/
│       ├── logging/
│       ├── aws_helper/
│       └── ...
└── use-cases/
    └── terraform-aws-lambda-layer/
        ├── main.tf
        └── build_layer.py
```

### Error: "Unknown module(s)"
Check that module names match exactly. Use `python build_layer.py --list` to see available modules:
```bash
cd terraform-aws-lambda-layer
python build_layer.py --list
```

### Layer Deployment Takes Too Long
Layer building is done via `local-exec`. If using remote backends with long latency:
- Ensure Python dependencies are pre-installed
- Consider building layers locally before Terraform apply
- Check network connectivity to Python package repositories

## Maintenance

### Updating ACAI Modules
When ACAI modules are updated:
1. Update the module version reference
2. The layer will automatically rebuild (detected via file hashing)
3. New layer version is created (old versions retained for rollback)

### Cleanup
Build artifacts are automatically cleaned between runs:
- `10-layer-source/` is recreated each build
- `20-zipped/` is recreated each build
- Set `skip_destroy = true` prevents layer deletion even with `terraform destroy`

## Examples

See [_example/](_example/) directory for complete working examples:
- [aws_organization](_example/aws_organization/) — Organizations helper layer
- [logging](_example/logging/) — Minimal layer with the ACAI `logging` module
- [logging_with_pip](_example/logging_with_pip/) — Layer combining ACAI modules with pip packages from `requirements.txt`
- [logging_with_inline](_example/logging_with_inline/) — Layer that bakes a custom `acme/logging_factory.py` helper into the layer via `inline_files` (folder-based)

See [_test/](/_test/) directory for integration tests:
- [terratest examples](/_test/terratest/)

## Security Considerations

- **Layer Immutability**: Each layer version is immutable; updates create new versions
- **Skip Destroy**: Production layers are protected from accidental `terraform destroy` deletion
- **Lambda Execution**: ACAI modules run with whatever IAM role is attached to Lambda functions
- **Dependencies**: All module dependencies are automatically resolved to prevent missing imports

## Testing

Run integration tests with Terratest:

```bash
cd _test/terratest
go test -v -timeout 30m
```

## Contributing

When adding new ACAI modules:
1. Update `DEPENDENCY_MAP` in `build_layer.py`
2. Add module to available modules table in README
3. Test with both `--list` and build operations
4. Update validation in `variables.tf`

## License

See [LICENSE.md](LICENSE.md) in the parent directory.

## Support

For issues, feature requests, or questions:
- Check the [troubleshooting section](#troubleshooting) above
- Review [_example/](/_example/) for usage patterns
- Run `python build_layer.py --list` to verify available modules
