variable "account_ids" {
  type = object({
    org_mgmt = string
    workload = string
  })
  description = "Account IDs for the different AWS accounts."
}

variable "aws_region" {
  type        = string
  description = "AWS region to use for all providers."
  default     = "eu-central-1"
}

variable "aws_partition" {
  type        = string
  description = "AWS partition to use for all providers."
  default     = "aws"
}

variable "aws_endpoint_domain" {
  type        = string
  description = "AWS endpoint domain to use for all providers (e.g. 'amazonaws.com' or 'amazonaws.eu')."
  default     = "amazonaws.com"
}

variable "iam_role_name" {
  type        = string
  description = "IAM role name to assume in each account."
  default     = "OrganizationAccountAccessRole"
}
