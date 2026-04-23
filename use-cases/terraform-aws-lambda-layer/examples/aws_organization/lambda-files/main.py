"""
Sample usage of acai OrganizationsHelper in a Lambda-like Python function.

This demonstrates leveraging the organization hexagon to retrieve and analyze
AWS Organizations hierarchy, accounts, and organizational units.
"""

import json

from acai.boto3_helper.organizations import OrganizationsHelper
from acai.logging import LoggerConfig, LoggerContext, LogLevel, create_lambda_logger

# Initialize logger
logger = create_lambda_logger(
    LoggerConfig(service_name="organizations-demo", log_level=LogLevel.DEBUG)
)


@logger.inject_lambda_context()
def lambda_handler(event, context):
    """
    Lambda handler demonstrating OrganizationsHelper usage.

    This function:
    1. Initializes the OrganizationsHelper
    2. Lists all AWS accounts
    3. Lists all child OUs
    4. Retrieves comprehensive account context
    5. Returns organization structure as JSON
    """
    logger.info("Lambda handler started.")
    logger.debug(f"Received event: {event}")

    try:
        # Initialize OrganizationsHelper
        org_helper = OrganizationsHelper(logger)
        logger.info(f"Organization ID: {org_helper.org_id}")

        # Get all accounts in the organization
        accounts = org_helper.list_accounts(only_active=True)
        logger.info(f"Found {len(accounts)} active accounts")

        with LoggerContext(logger, {"operation": "list_accounts"}):
            logger.debug(f"Accounts: {list(accounts.keys())}")

        # Get all roots
        roots = org_helper.roots
        logger.info(f"Found {len(roots)} organizational roots")

        with LoggerContext(logger, {"operation": "list_roots"}):
            for root_id, root in roots.items():
                logger.debug(f"Root ID: {root_id}, Name: {root.get('Name', 'N/A')}")

                # List all child OUs under this root
                child_ous = org_helper.list_child_ous(root_id, include_root=True)
                logger.info(f"Found {len(child_ous)} OUs under {root_id}")

        # Get comprehensive context for each account
        account_contexts = []
        for account_id in accounts.keys():
            with LoggerContext(logger, {"account_id": account_id}):
                context_info = org_helper.get_member_account_context(account_id)
                if context_info:
                    account_contexts.append(context_info)
                    logger.debug(
                        f"Account context retrieved: {context_info.get('accountName')}"
                    )

        logger.info(f"Retrieved context for {len(account_contexts)} accounts")

        # Debug: Log cache contents
        org_helper.debug_info()

        # Prepare result
        result = {
            "message": "Organization data retrieved successfully",
            "organization_id": org_helper.org_id,
            "total_accounts": len(accounts),
            "total_roots": len(roots),
            "account_count_with_context": len(account_contexts),
            "accounts": {
                account_id: {
                    "name": account.get("Name", "N/A"),
                    "status": account.get("Status", "N/A"),
                    "email": account.get("Email", "N/A"),
                }
                for account_id, account in accounts.items()
            },
            "account_contexts": account_contexts,
        }

        logger.info("Processing successful.")
        return result

    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Example local test
    sample_event = {"test": "local"}
    result = lambda_handler(sample_event, None)
    print(json.dumps(result, indent=2))
