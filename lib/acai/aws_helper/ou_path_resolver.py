from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any, Iterator
from urllib.parse import urlparse

import boto3
from botocore.config import Config as boto3_config


class OuPathResolver:
    """Resolve OU path strings to AWS Organizations OU IDs.

    Standalone helper — no acai package dependencies required.
    Accepts any logger with ``debug``/``info``/``error`` methods
    (stdlib ``logging.Logger``, acai ``Loggable``, etc.).
    """

    def __init__(self, logger: Any, org_client: Any) -> None:
        self.logger = logger
        self.org_client = org_client
        self.org_id = self._get_organization_id()
        self.roots = self._get_organization_roots()

    def validate_org(self, expected_org_id: str, expected_root_ou_id: str) -> None:
        """Raise ``ValueError`` when org ID or root OU ID don't match.

        Example::

            resolver.validate_org(
                expected_org_id="o-12345",
                expected_root_ou_id="r-ab12",
            )
            # raises ValueError if the current session belongs to a different org
        """
        found_root_ou_id = next(iter(self.roots), None)
        if (expected_org_id != self.org_id) or (expected_root_ou_id not in self.roots):
            raise ValueError(
                f"Not in the correct AWS Org. Required: {expected_org_id}/{expected_root_ou_id} "
                f"Found: {self.org_id}/{found_root_ou_id}"
            )

    def resolve_ou_tree(self) -> dict[str, dict[str, Any]]:
        """Walk the full OU tree and return every OU path with its ID and level.

        Returns:
            ``{"/root/": {"ou_id": "r-xxxx", "level": 0}, ...}``

        Example output::

            {
                "/root/":                {"ou_id": "r-ab12",          "level": 0},
                "/root/Core/":           {"ou_id": "ou-ab12-00000001", "level": 1},
                "/root/Core/Security/":  {"ou_id": "ou-ab12-12345678", "level": 2},
                "/root/Workloads/":      {"ou_id": "ou-ab12-00000002", "level": 1},
                "/root/Workloads/Prod/": {"ou_id": "ou-ab12-87654321", "level": 2},
            }
        """
        root_ou_id = next(iter(self.roots)) if self.roots else None
        if not root_ou_id or not self.org_id:
            self.logger.error("Cannot resolve OU tree: org_id or root unknown")
            return {}

        self.logger.debug("Walking full OU tree")
        result: dict[str, dict[str, Any]] = {
            "/root/": {"ou_id": root_ou_id, "level": 0}
        }
        self._walk_ou_tree(root_ou_id, "/root", 1, result)
        self.logger.info(f"OU tree contains {len(result)} nodes")
        return result

    def resolve_ou_paths(self, ou_paths: list[str]) -> dict[str, dict[str, str]]:
        """Resolve OU path strings to OU IDs with metadata.

        Accepts a list of OU paths and returns a dict keyed by resolved path name.

        Paths may start with ``/root/...``, ``/...`` (implicit root), or
        bare ``a/b/c`` (implicit root and leading slash).
        Supports wildcard ``*`` segments to match all child OUs at that level.

        Args:
            ou_paths: ``["/root/Path", "/Workloads/Prod", "Core/Security", ...]``

        Example input::

            [
                "/root/Core/Security/",
                "/Workloads/Prod/",
                "Sandbox/",
                "/root/",
                "/root/Workloads/*",
            ]

        Returns:
            ``{<path>: {"ou_id": str, "ou_id_path": str}, ...}``

        Example output::

            {
                "/root/Core/Security/": {
                    "ou_id":      "ou-ab12-12345678",
                    "ou_id_path": "o-12345/r-ab12/ou-ab12-00000001/ou-ab12-12345678",
                },
                "/root/Workloads/Prod/": {
                    "ou_id":      "ou-ab12-87654321",
                    "ou_id_path": "o-12345/r-ab12/ou-ab12-00000002/ou-ab12-87654321",
                },
                "/root/": {
                    "ou_id":      "r-ab12",
                    "ou_id_path": "o-12345/r-ab12",
                },
                "/root/Workloads/TeamA/": {
                    "ou_id":      "ou-ab12-11111111",
                    "ou_id_path": "o-12345/r-ab12/ou-ab12-00000002/ou-ab12-11111111",
                },
                "/root/Workloads/TeamB/": {
                    "ou_id":      "ou-ab12-22222222",
                    "ou_id_path": "o-12345/r-ab12/ou-ab12-00000002/ou-ab12-22222222",
                },
            }
        """
        root_ou_id = next(iter(self.roots)) if self.roots else None
        if not root_ou_id or not self.org_id:
            self.logger.error("Cannot resolve OU paths: org_id or root unknown")
            return {}

        self.logger.debug(f"Resolving {len(ou_paths)} OU paths")
        ou_results: dict[str, dict[str, str]] = {}

        for path in ou_paths:
            path = self._normalize_path(path)

            if path == "/root":
                if "/root/" not in ou_results:
                    ou_results["/root/"] = {
                        "ou_id": root_ou_id,
                        "ou_id_path": f"{self.org_id}/{root_ou_id}",
                    }
            else:
                normalized = path[len("/root") :]  # noqa: E203 (black slice spacing)
                ous = self._resolve_ous_by_path(
                    root_ou_id, normalized, "/root", f"{self.org_id}/{root_ou_id}"
                )
                for ou in ous:
                    key = ou["path_name"] + "/"
                    if key not in ou_results:
                        ou_results[key] = {
                            "ou_id": ou["id"],
                            "ou_id_path": ou["path_id"],
                        }

        self.logger.info(f"Resolved {len(ou_results)} OU targets")
        return ou_results

    def resolve_ou_paths_with_assignments(
        self, ou_assignments: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Resolve OU path strings to OU IDs, carrying assignment payloads along.

        Accepts a mapping of OU paths to arbitrary assignment payloads
        and returns a dict keyed by resolved path (with trailing ``/``).

        Paths may start with ``/root/...``, ``/...`` (implicit root), or
        bare ``a/b/c`` (implicit root and leading slash).
        Supports wildcard ``*`` segments to match all child OUs at that level.
        When multiple input paths resolve to the same OU, their assignments
        are merged into a single list.

        Args:
            ou_assignments: ``{"/root/Path": <assignments>, ...}``

        Example input::

            {
                "/root/Core/Security": {"scp": "deny-all"},
                "/Workloads/Prod":     {"scp": "restrict"},
                "/root":               {"scp": "base"},
                "/root/Workloads/*":   {"scp": "audit"},
            }

        Returns:
            ``{<path>: {"ou_id": str, "ou_id_path": str, "assignments": list}, ...}``

        Example output::

            {
                "/root/Core/Security/": {
                    "ou_id":       "ou-ab12-12345678",
                    "ou_id_path":  "o-12345/r-ab12/ou-ab12-00000001/ou-ab12-12345678",
                    "assignments": [{"scp": "deny-all"}],
                },
                "/root/Workloads/Prod/": {
                    "ou_id":       "ou-ab12-87654321",
                    "ou_id_path":  "o-12345/r-ab12/ou-ab12-00000002/ou-ab12-87654321",
                    "assignments": [{"scp": "restrict"}],
                },
                "/root/": {
                    "ou_id":       "r-ab12",
                    "ou_id_path":  "o-12345/r-ab12",
                    "assignments": [{"scp": "base"}],
                },
                "/root/Workloads/TeamA/": {
                    "ou_id":       "ou-ab12-11111111",
                    "ou_id_path":  "o-12345/r-ab12/ou-ab12-00000002/ou-ab12-11111111",
                    "assignments": [{"scp": "audit"}],
                },
                "/root/Workloads/TeamB/": {
                    "ou_id":       "ou-ab12-22222222",
                    "ou_id_path":  "o-12345/r-ab12/ou-ab12-00000002/ou-ab12-22222222",
                    "assignments": [{"scp": "audit"}],
                },
            }
        """
        resolved = self.resolve_ou_paths(list(ou_assignments.keys()))
        ou_results: dict[str, dict[str, Any]] = {}

        for input_path, assignments in ou_assignments.items():
            assignments_list: list[Any] = (
                assignments if isinstance(assignments, list) else [assignments]
            )
            normalized_key = self._normalize_path(input_path) + "/"
            # Fast path: exact match (no wildcard)
            if "*" not in normalized_key and normalized_key in resolved:
                target = ou_results.setdefault(
                    normalized_key,
                    {**resolved[normalized_key], "assignments": []},
                )
                target["assignments"].extend(assignments_list)
                continue
            # Wildcard match: same depth, '*' matches any segment
            input_parts = normalized_key.strip("/").split("/")
            for key, info in resolved.items():
                key_parts = key.strip("/").split("/")
                if len(input_parts) == len(key_parts) and all(
                    i == k or i == "*" for i, k in zip(input_parts, key_parts)
                ):
                    target = ou_results.setdefault(key, {**info, "assignments": []})
                    target["assignments"].extend(assignments_list)

        self.logger.info(f"Resolved {len(ou_results)} OU targets")
        return ou_results

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------
    _MULTI_SLASH = re.compile(r"/+")

    def _normalize_path(self, path: str) -> str:
        """Normalize a user-supplied OU path to ``/root/...`` form.

        Collapses repeated slashes and accepts ``/root/x``, ``/x``, or ``x``.
        """
        path = self._MULTI_SLASH.sub("/", path).strip("/")
        if path == "" or path == "root":
            return "/root"
        if not path.startswith("root/"):
            return "/root/" + path
        return "/" + path

    def _get_organization_id(self) -> str | None:
        try:
            response = self.org_client.describe_organization()
            return response["Organization"]["Id"]
        except Exception as e:
            self.logger.error(f"Error getting organization ID: {e}")
            raise

    def _get_organization_roots(self) -> dict[str, Any]:
        try:
            roots: dict[str, Any] = {}
            response = self.org_client.list_roots()
            for root in response["Roots"]:
                roots[root["Id"]] = root
            return roots
        except Exception as e:
            self.logger.error(f"Error getting organization roots: {e}")
            raise

    def _list_child_ous(self, parent_id: str) -> Iterator[dict[str, Any]]:
        """Yield every child OU of *parent_id*, paginating transparently."""
        paginator = self.org_client.get_paginator(
            "list_organizational_units_for_parent"
        )
        for page in paginator.paginate(ParentId=parent_id):
            yield from page["OrganizationalUnits"]

    def _resolve_ous_by_path(
        self,
        parent_ou_id: str,
        remaining_ou_path: str,
        current_path_name: str,
        current_path_id: str,
    ) -> list[dict[str, str]]:
        parts = remaining_ou_path.strip("/").split("/")
        segment = parts[0]

        found_ous: list[dict[str, str]] = [
            {
                "id": ou["Id"],
                "name": ou["Name"],
                "path_name": f'{current_path_name}/{ou["Name"]}',
                "path_id": f'{current_path_id}/{ou["Id"]}',
            }
            for ou in self._list_child_ous(parent_ou_id)
            if segment == "*" or ou["Name"] == segment
        ]

        if len(parts) == 1:
            return found_ous

        rest_of_path = "/" + "/".join(parts[1:])
        results: list[dict[str, str]] = []
        for matched in found_ous:
            results.extend(
                self._resolve_ous_by_path(
                    matched["id"],
                    rest_of_path,
                    matched["path_name"],
                    matched["path_id"],
                )
            )
        return results

    def _walk_ou_tree(
        self,
        parent_id: str,
        parent_path: str,
        current_level: int,
        result: dict[str, dict[str, Any]],
    ) -> None:
        for ou in self._list_child_ous(parent_id):
            child_path = f"{parent_path}/{ou['Name']}"
            result[f"{child_path}/"] = {
                "ou_id": ou["Id"],
                "level": current_level,
            }
            self._walk_ou_tree(ou["Id"], child_path, current_level + 1, result)


# ---------------------------------------------------------------------------
# Shared CLI helpers — used by Terraform external-data wrapper scripts
# ---------------------------------------------------------------------------
def create_organizations_client(
    endpoint_url: str | None = None,
    role_arn: str | None = None,
    region_name: str | None = None,
) -> Any:
    """Create a boto3 Organizations client with standard retry config.

    Handles optional cross-account role assumption and endpoint URL override
    (e.g. for AWS ESC partitions). When *region_name* is omitted and
    *endpoint_url* is given, the region is best-effort parsed from the host
    name (``service.<region>.amazonaws.com``); pass *region_name* explicitly
    for non-standard hostnames (FIPS, dualstack, global endpoints).

    Examples::

        # Default — uses current session credentials
        client = create_organizations_client()

        # Cross-account with role assumption
        client = create_organizations_client(
            role_arn="arn:aws:iam::123456789012:role/OrgReadOnly",
        )

        # Custom endpoint (e.g. AWS ESC partition)
        client = create_organizations_client(
            endpoint_url="https://organizations.eu-central-1.amazonaws.com",
            region_name="eu-central-1",
        )
    """
    session = _assume_remote_role(role_arn) if role_arn else boto3.Session()

    config = boto3_config(
        retries={"max_attempts": 10, "mode": "standard"},
        connect_timeout=10,
        read_timeout=30,
    )
    client_kwargs: dict[str, Any] = {"config": config}
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
        if not region_name:
            region_name = _region_from_endpoint(endpoint_url)
    if region_name:
        client_kwargs["region_name"] = region_name
    return session.client("organizations", **client_kwargs)


def _region_from_endpoint(endpoint_url: str) -> str | None:
    """Best-effort extract a region from ``service.<region>.amazonaws.com``."""
    host = urlparse(endpoint_url).hostname or ""
    parts = host.split(".")
    # Expect at minimum: <service>.<region>.amazonaws.com
    if len(parts) >= 4 and parts[-2:] == ["amazonaws", "com"]:
        return parts[-3]
    return None


def terraform_json_output(result: Any) -> None:
    """Print *result* as ``{"result": "<json-string>"}`` for Terraform external data.

    Example::

        terraform_json_output({"ou_id": "ou-ab12-12345678"})
        # stdout: {"result": "{\\"ou_id\\": \\"ou-ab12-12345678\\"}"}
    """
    sys.stdout.write(json.dumps({"result": json.dumps(result)}) + "\n")
    sys.stdout.flush()


def _assume_remote_role(remote_role_arn: str) -> boto3.Session:
    try:
        sts_client = boto3.client("sts")
        response = sts_client.assume_role(
            RoleArn=remote_role_arn, RoleSessionName="RemoteSession"
        )
    except Exception as e:
        logging.getLogger(__name__).error(
            "Failed to assume role %s: %s", remote_role_arn, e
        )
        raise RuntimeError(f"Was not able to assume role {remote_role_arn}") from e
    return boto3.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )
