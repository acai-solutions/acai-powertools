from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3

from acai.aws_helper.ou_path_resolver import OuPathResolver

if TYPE_CHECKING:
    from acai.logging import Loggable


class OrganizationsHelper(OuPathResolver):
    """Helper class for AWS Organizations operations with caching support.

    Extends :class:`OuPathResolver` — inherits ``validate_org``,
    ``resolve_ou_paths``, ``resolve_ou_tree``, and the private helpers
    ``_get_organization_id``, ``_get_organization_roots``,
    ``_resolve_ous_by_path``, ``_walk_ou_tree``.
    """

    def __init__(self, logger: Loggable, org_client: Any = None):
        """Initialize the OrganizationsHelper.

        Args:
            logger: Logger instance for debug/info/warning messages
            org_client: Optional boto3 Organizations client. If not provided, creates one.
        """
        super().__init__(logger, org_client or boto3.client("organizations"))
        self._parents_cache: dict[str, tuple[str, str]] = {}
        self.ou_id_with_path_cache: dict[str, tuple[str, str]] = {}
        self.ou_name_cache: dict[str, str] = {}
        self.ou_name_with_path_cache: dict[str, tuple[str, str]] = {}
        self.ou_tags_cache: dict[str, dict[str, str]] = {}

    def list_accounts(self, only_active: bool = True) -> dict[str, dict[str, Any]]:
        """List all accounts in the organisation, keyed by account ID."""
        self.logger.debug(
            "Listing organisation accounts" + (" (active only)" if only_active else "")
        )
        result: dict[str, dict[str, Any]] = {}
        paginator = self.org_client.get_paginator("list_accounts")
        for page in paginator.paginate():
            for account in page["Accounts"]:
                if only_active and account["Status"] != "ACTIVE":
                    continue
                account.pop("JoinedTimestamp", None)
                result[account["Id"]] = account
        self.logger.info(f"Listed {len(result)} accounts")
        return result

    def list_account_ids(self, only_active: bool = True) -> list[str]:
        """Return a list of account IDs."""
        accounts = self.list_accounts(only_active)
        return list(accounts.keys())

    def list_accounts_for_parent(self, parent_id: str) -> dict[str, dict[str, Any]]:
        """List accounts directly under *parent_id*."""
        self.logger.debug(f"Listing accounts for parent {parent_id}")
        result: dict[str, dict[str, Any]] = {}
        paginator = self.org_client.get_paginator("list_accounts_for_parent")
        for page in paginator.paginate(ParentId=parent_id):
            for account in page["Accounts"]:
                account.pop("JoinedTimestamp", None)
                result[account["Id"]] = account
        self.logger.debug(f"Found {len(result)} accounts under {parent_id}")
        return result

    def list_child_ous(self, parent_ou_id: str, include_root: bool = True) -> list[str]:
        """Recursively list all child OU IDs under *parent_ou_id*."""
        self.logger.debug(f"Listing child OUs for {parent_ou_id}")
        result: list[str] = []
        if include_root:
            result.append(parent_ou_id)

        paginator = self.org_client.get_paginator("list_children")
        direct_children: list[str] = []
        for page in paginator.paginate(
            ParentId=parent_ou_id, ChildType="ORGANIZATIONAL_UNIT"
        ):
            for child in page["Children"]:
                result.append(child["Id"])
                direct_children.append(child["Id"])

        for child_ou in direct_children:
            result.extend(self.list_child_ous(child_ou, include_root=False))

        self.logger.debug(f"Found {len(result)} OUs under {parent_ou_id}")
        return result

    def list_all_accounts_by_list(
        self,
        ou_list: list[str],
        org_master_account_id: str,
        without_suspended: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """List all accounts in given OUs, including the management account."""
        self.logger.debug(f"Listing accounts across {len(ou_list)} OUs")
        result: dict[str, dict[str, Any]] = {}

        master_response = self.org_client.describe_account(
            AccountId=org_master_account_id
        )
        if "Account" in master_response:
            master = master_response["Account"]
            master.pop("JoinedTimestamp", None)
            result[org_master_account_id] = master

        for ou_id in ou_list:
            accounts = self.list_accounts_for_parent(ou_id)
            for account_id, account in accounts.items():
                if without_suspended and account["Status"] == "SUSPENDED":
                    continue
                result[account_id] = account

        self.logger.info(f"Listed {len(result)} accounts across {len(ou_list)} OUs")
        return result

    def list_all_accounts_by_parent(
        self,
        parent_ou_id: str,
        org_master_account_id: str,
        without_suspended: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """List all accounts under *parent_ou_id* (recursively), including management account."""
        self.logger.debug(f"Listing all accounts under parent OU {parent_ou_id}")
        ous = self.list_child_ous(parent_ou_id, include_root=True)
        return self.list_all_accounts_by_list(
            ous, org_master_account_id, without_suspended
        )

    def get_ou_id(self, account_id: str) -> str | None:
        """Return the parent OU ID for an account."""
        if account_id in self._parents_cache:
            return self._parents_cache[account_id]

        self.logger.debug(f"Getting parent OU for account {account_id}")
        response = self.org_client.list_parents(ChildId=account_id)
        parents = response.get("Parents", [])
        if len(parents) == 1:
            ou_id = parents[0]["Id"]
            self._parents_cache[account_id] = ou_id
            return ou_id
        self.logger.warning(
            f"Expected 1 parent for account {account_id}, got {len(parents)}"
        )
        return None

    def get_tags(self, account_id: str) -> dict[str, str]:
        """Return all tags for a resource as a flat dict."""
        self.logger.debug(f"Getting tags for {account_id}")
        tags: dict[str, str] = {}
        try:
            paginator = self.org_client.get_paginator("list_tags_for_resource")
            for page in paginator.paginate(ResourceId=account_id):
                for entry in page["Tags"]:
                    tags[entry["Key"]] = entry["Value"]
            self.logger.debug(f"Found {len(tags)} tags for {account_id}")
        except Exception as e:
            self.logger.error(f"Error getting tags for {account_id}: {e}")
            raise
        return tags

    def get_member_account_context(
        self, member_account_id: str
    ) -> dict[str, Any] | None:
        """Get comprehensive context for an account.

        Returns dict with:
        - accountId, accountName, accountStatus, accountTags
        - ouId, ouIdWithPath, ouName, ouNameWithPath
        - ouTags
        """
        account_info = self._describe_account(member_account_id)
        if not account_info:
            return None

        account = account_info.get("Account", {})
        account_name = account.get("Name", "n/a")
        account_status = account.get("Status", "n/a")
        caller_ou_id, caller_ou_id_with_path = self._get_ou_id_with_path(
            member_account_id
        )
        caller_ou_name, caller_ou_name_with_path = self._get_ou_name_with_path(
            member_account_id
        )
        caller_account_tags = self._get_tags(member_account_id)
        ou_tags = self._get_tags(caller_ou_id) if caller_ou_id else {}

        return {
            "accountId": member_account_id,
            "accountName": account_name,
            "accountStatus": account_status,
            "accountTags": caller_account_tags,
            "ouId": caller_ou_id,
            "ouIdWithPath": caller_ou_id_with_path,
            "ouName": caller_ou_name,
            "ouNameWithPath": caller_ou_name_with_path,
            "ouTags": ou_tags,
        }

    def debug_info(self) -> None:
        """Log cache contents for debugging."""
        self.logger.info(f"ou_id_with_path_cache={self.ou_id_with_path_cache}")
        self.logger.info(f"ou_name_cache={self.ou_name_cache}")
        self.logger.info(f"ou_name_with_path_cache={self.ou_name_with_path_cache}")

    # -------------------------------------------------------------------------
    # Private helpers (account-centric — not in OuPathResolver)
    # -------------------------------------------------------------------------
    def _describe_account(self, account_id: str) -> dict[str, Any]:
        """Describe an account; raises on AWS errors."""
        try:
            return self.org_client.describe_account(AccountId=account_id)
        except Exception as e:
            self.logger.error(f"Error describing account {account_id}: {e}")
            raise

    def _get_parent_ou(self, child_id: str) -> tuple[str | None, str]:
        """Get parent OU ID and type for a child resource."""
        if not child_id:
            raise ValueError("_get_parent_ou called with empty child_id")
        if child_id in self.roots:
            return None, "ROOT"
        if child_id in self._parents_cache:
            return self._parents_cache[child_id]

        try:
            parents = self.org_client.list_parents(ChildId=child_id)
            parent = parents["Parents"][0]
            parent_ou_id = parent["Id"]
            parent_type = parent["Type"]
            self._parents_cache[child_id] = (parent_ou_id, parent_type)
            return parent_ou_id, parent_type
        except Exception as e:
            self.logger.error(f"Error getting parent OU for {child_id}: {e}")
            raise

    def _get_ou_name(self, ou_id: str) -> str:
        """Get the name of an OU."""
        if ou_id in self.ou_name_cache:
            return self.ou_name_cache[ou_id]

        try:
            response = self.org_client.describe_organizational_unit(
                OrganizationalUnitId=ou_id
            )
            ou_name = response["OrganizationalUnit"].get("Name", "")
            self.ou_name_cache[ou_id] = ou_name
            return ou_name
        except Exception as e:
            self.logger.error(f"Error getting OU name for {ou_id}: {e}")
            raise

    def _get_ou_id_with_path(self, account_id: str) -> tuple[str, str]:
        """Get the OU ID and its path (e.g., /org-id/ou-1/ou-2/)."""
        ou_id_path: list[str] = []
        direct_parent_ou_id, parent_type = self._get_parent_ou(account_id)

        if direct_parent_ou_id in self.ou_id_with_path_cache:
            return self.ou_id_with_path_cache[direct_parent_ou_id]

        parent_ou_id = direct_parent_ou_id
        if not parent_ou_id:
            return "", ""

        while True:
            ou_id_path.append(parent_ou_id)
            if parent_type == "ROOT":
                ou_id_path_str = f'/{self.org_id}/{"/".join(reversed(ou_id_path))}/'
                self.ou_id_with_path_cache[direct_parent_ou_id] = (
                    direct_parent_ou_id,
                    ou_id_path_str,
                )
                return direct_parent_ou_id, ou_id_path_str
            parent_ou_id, parent_type = self._get_parent_ou(parent_ou_id)
            if not parent_ou_id:
                return "", ""

    def _get_ou_name_with_path(self, account_id: str) -> tuple[str, str]:
        """Get the OU name and its path (e.g., /root/prod/security/)."""
        ou_name_path: list[str] = []
        direct_parent_ou_id, parent_type = self._get_parent_ou(account_id)

        if not direct_parent_ou_id:
            return "", ""

        if direct_parent_ou_id in self.ou_name_with_path_cache:
            return self.ou_name_with_path_cache[direct_parent_ou_id]

        direct_parent_ou_name = (
            "root"
            if parent_type == "ROOT"
            else self._get_ou_name(direct_parent_ou_id)
        )
        parent_ou_id = direct_parent_ou_id

        while True:
            parent_ou_name = (
                "root" if parent_type == "ROOT" else self._get_ou_name(parent_ou_id)
            )
            ou_name_path.append(parent_ou_name)
            if parent_type == "ROOT":
                ou_name_path_str = "/" + "/".join(reversed(ou_name_path)) + "/"
                self.ou_name_with_path_cache[direct_parent_ou_id] = (
                    direct_parent_ou_name,
                    ou_name_path_str,
                )
                return direct_parent_ou_name, ou_name_path_str
            parent_ou_id, parent_type = self._get_parent_ou(parent_ou_id)
            if not parent_ou_id:
                return "", ""

    def _get_tags(self, resource_id: str) -> dict[str, str]:
        """Get tags for a resource with caching."""
        if resource_id in self.ou_tags_cache:
            return self.ou_tags_cache[resource_id]

        tags: dict[str, str] = {}
        paginator = self.org_client.get_paginator("list_tags_for_resource")
        try:
            for page in paginator.paginate(ResourceId=resource_id):
                for entry in page.get("Tags", []):
                    tags[entry["Key"]] = entry["Value"]
            self.ou_tags_cache[resource_id] = tags
        except Exception as e:
            self.logger.error(f"Error getting tags for resource {resource_id}: {e}")
            raise
        return tags


# Backward compatibility: module-level functions that wrap the class
def organizations_list_accounts(
    org_client: Any, logger: Loggable, only_active: bool = True
) -> dict[str, dict[str, Any]]:
    """List all accounts in the organisation, keyed by account ID."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.list_accounts(only_active)


def organizations_list_account_ids(
    org_client: Any, logger: Loggable, only_active: bool = True
) -> list[str]:
    """Return a list of account IDs."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.list_account_ids(only_active)


def organizations_list_accounts_for_parent(
    org_client: Any, logger: Loggable, parent_id: str
) -> dict[str, dict[str, Any]]:
    """List accounts directly under *parent_id*."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.list_accounts_for_parent(parent_id)


def organizations_list_child_ous(
    org_client: Any, logger: Loggable, parent_ou_id: str, include_root: bool = True
) -> list[str]:
    """Recursively list all child OU IDs under *parent_ou_id*."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.list_child_ous(parent_ou_id, include_root)


def organizations_list_all_accounts_by_list(
    org_client: Any,
    logger: Loggable,
    ou_list: list[str],
    org_master_account_id: str,
    without_suspended: bool = False,
) -> dict[str, dict[str, Any]]:
    """List all accounts in given OUs, including the management account."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.list_all_accounts_by_list(
        ou_list, org_master_account_id, without_suspended
    )


def organizations_list_all_accounts_by_parent(
    org_client: Any,
    logger: Loggable,
    parent_ou_id: str,
    org_master_account_id: str,
    without_suspended: bool = False,
) -> dict[str, dict[str, Any]]:
    """List all accounts under *parent_ou_id* (recursively), including management account."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.list_all_accounts_by_parent(
        parent_ou_id, org_master_account_id, without_suspended
    )


def organizations_get_ou_id(
    org_client: Any, logger: Loggable, account_id: str
) -> str | None:
    """Return the parent OU ID for an account."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.get_ou_id(account_id)


def organizations_get_tags(
    org_client: Any, logger: Loggable, account_id: str
) -> dict[str, str]:
    """Return all tags for a resource as a flat dict."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.get_tags(account_id)


def organizations_get_member_account_context(
    org_client: Any, logger: Loggable, member_account_id: str
) -> dict[str, Any] | None:
    """Get comprehensive context for an account."""
    helper = OrganizationsHelper(logger, org_client)
    return helper.get_member_account_context(member_account_id)
