import unittest
from unittest.mock import MagicMock, patch

from acai.aws_helper.boto3_client import (
    Boto3ClientFactory,
    get_aws_client,
    get_boto3_resource,
)
from acai.aws_helper.organizations import (
    OrganizationsHelper,
    organizations_get_member_account_context,
    organizations_get_ou_id,
    organizations_get_tags,
    organizations_list_account_ids,
    organizations_list_accounts,
    organizations_list_child_ous,
)
from acai.aws_helper.s3 import S3ObjectManager
from acai.aws_helper.sns import SnsClient, send_to_sns
from acai.aws_helper.sts import StsClient


# ---------------------------------------------------------------------------
# Stub logger
# ---------------------------------------------------------------------------
class _Logger:
    def info(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


# ---------------------------------------------------------------------------
# S3ObjectManager — static / pure methods
# ---------------------------------------------------------------------------
class TestS3StaticMethods(unittest.TestCase):
    def test_get_full_path(self):
        self.assertEqual(S3ObjectManager.get_full_path("a/b/c/file.txt"), "a/b/c")

    def test_get_full_path_root(self):
        self.assertEqual(S3ObjectManager.get_full_path("file.txt"), "")

    def test_get_parent_folder_name(self):
        self.assertEqual(S3ObjectManager.get_parent_folder_name("a/b/c/file.txt"), "c")

    def test_get_parent_folder_name_shallow(self):
        self.assertEqual(S3ObjectManager.get_parent_folder_name("a/file.txt"), "a")

    def test_get_parent_folder_name_root(self):
        self.assertEqual(S3ObjectManager.get_parent_folder_name("file.txt"), "")

    def test_get_object_name(self):
        self.assertEqual(S3ObjectManager.get_object_name("a/b/file.txt"), "file.txt")

    def test_get_object_name_no_path(self):
        self.assertEqual(S3ObjectManager.get_object_name("file.txt"), "file.txt")


class TestS3Cache(unittest.TestCase):
    def test_get_local_cache_empty(self):
        resource = MagicMock()
        mgr = S3ObjectManager(_Logger(), resource)
        self.assertEqual(mgr.get_local_cache(), {})

    def test_put_and_get_cached(self):
        resource = MagicMock()
        s3_obj = MagicMock()
        s3_obj.last_modified = "2025-01-01"
        resource.Object.return_value = s3_obj
        s3_obj.put.return_value = {}

        mgr = S3ObjectManager(_Logger(), resource)
        mgr.put_object_to_bucket("bucket", "key.txt", b"data")

        self.assertEqual(mgr.cache["key.txt"], b"data")
        self.assertIn("key.txt", mgr.last_modified_cache)

    def test_get_cached_object_404(self):
        import botocore.exceptions

        resource = MagicMock()
        resource.ObjectSummary.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "404"}}, "GetObject"
        )
        resource.Object.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "404"}}, "GetObject"
        )

        mgr = S3ObjectManager(_Logger(), resource)
        result = mgr.get_cached_object("bucket", "missing.txt")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# StsClient
# ---------------------------------------------------------------------------
class TestStsClient(unittest.TestCase):
    def test_assume_role_success(self):
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIA...",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            }
        }

        client = StsClient(_Logger(), base_session=mock_session)
        with patch("acai.aws_helper.sts.boto3.Session") as mock_boto_session:
            session = client.assume_role("arn:aws:iam::123:role/Test", "eu-central-1")
            mock_boto_session.assert_called_once()
            self.assertIsNotNone(session)

    def test_assume_role_failure_returns_none(self):
        mock_session = MagicMock()
        mock_session.client.side_effect = Exception("no access")

        client = StsClient(_Logger(), base_session=mock_session)
        result = client.assume_role("arn:aws:iam::123:role/Nope")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Boto3ClientFactory
# ---------------------------------------------------------------------------
class TestBoto3ClientFactory(unittest.TestCase):
    @patch("acai.aws_helper.boto3_client.boto3.client")
    def test_get_client_success(self, mock_boto_client):
        mock_boto_client.return_value = MagicMock()

        factory = Boto3ClientFactory(_Logger(), region="eu-central-1")
        client = factory.get_client("s3")

        self.assertIsNotNone(client)
        mock_boto_client.assert_called_once()
        call_kwargs = mock_boto_client.call_args
        self.assertEqual(call_kwargs[0][0], "s3")
        self.assertEqual(call_kwargs[1]["region_name"], "eu-central-1")

    @patch("acai.aws_helper.boto3_client.boto3.client")
    def test_get_client_region_override(self, mock_boto_client):
        mock_boto_client.return_value = MagicMock()

        factory = Boto3ClientFactory(_Logger(), region="eu-central-1")
        factory.get_client("s3", region="us-west-2")

        call_kwargs = mock_boto_client.call_args
        self.assertEqual(call_kwargs[1]["region_name"], "us-west-2")

    @patch("acai.aws_helper.boto3_client.boto3.client")
    def test_get_client_no_credentials(self, mock_boto_client):
        from botocore.exceptions import NoCredentialsError

        mock_boto_client.side_effect = NoCredentialsError()

        factory = Boto3ClientFactory(_Logger())
        with self.assertRaises(NoCredentialsError):
            factory.get_client("s3")

    @patch("acai.aws_helper.boto3_client.boto3.resource")
    def test_get_resource_success(self, mock_boto_resource):
        mock_boto_resource.return_value = MagicMock()

        factory = Boto3ClientFactory(_Logger(), region="eu-central-1")
        resource = factory.get_resource("s3")

        self.assertIsNotNone(resource)
        mock_boto_resource.assert_called_once()

    @patch("acai.aws_helper.boto3_client.boto3.resource")
    def test_get_resource_failure(self, mock_boto_resource):
        mock_boto_resource.side_effect = Exception("boom")

        factory = Boto3ClientFactory(_Logger())
        with self.assertRaises(Exception):
            factory.get_resource("s3")


class TestBoto3ClientBackwardCompat(unittest.TestCase):
    @patch("acai.aws_helper.boto3_client.boto3.client")
    def test_get_aws_client_function(self, mock_boto_client):
        mock_boto_client.return_value = MagicMock()

        client = get_aws_client(_Logger(), "s3", region="eu-central-1")
        self.assertIsNotNone(client)

    @patch("acai.aws_helper.boto3_client.boto3.resource")
    def test_get_boto3_resource_function(self, mock_boto_resource):
        mock_boto_resource.return_value = MagicMock()

        resource = get_boto3_resource(_Logger(), "s3", region="eu-central-1")
        self.assertIsNotNone(resource)


# ---------------------------------------------------------------------------
# SNS
# ---------------------------------------------------------------------------
class TestSnsClient(unittest.TestCase):
    def test_publish_success(self):
        mock_boto = MagicMock()
        mock_boto.publish.return_value = {"MessageId": "abc123"}

        client = SnsClient(_Logger(), mock_boto)
        result = client.publish("arn:aws:sns:eu:123:topic", "Subject", {"key": "val"})
        self.assertEqual(result["MessageId"], "abc123")
        mock_boto.publish.assert_called_once()

    def test_publish_failure_returns_none(self):
        mock_boto = MagicMock()
        mock_boto.publish.side_effect = Exception("network error")

        client = SnsClient(_Logger(), mock_boto)
        result = client.publish("arn:aws:sns:eu:123:topic", "Subject", {})
        self.assertIsNone(result)

    def test_publish_with_attributes(self):
        mock_boto = MagicMock()
        mock_boto.publish.return_value = {"MessageId": "xyz"}

        client = SnsClient(_Logger(), mock_boto)
        attrs = {"env": {"DataType": "String", "StringValue": "prod"}}
        result = client.publish(
            "arn:aws:sns:eu:123:topic", "Subject", {"key": "val"}, attrs
        )
        self.assertEqual(result["MessageId"], "xyz")
        call_kwargs = mock_boto.publish.call_args[1]
        self.assertEqual(call_kwargs["MessageAttributes"], attrs)


class TestSnsBackwardCompat(unittest.TestCase):
    def test_send_to_sns_function(self):
        mock_client = MagicMock()
        mock_client.publish.return_value = {"MessageId": "abc123"}

        result = send_to_sns(
            _Logger(),
            mock_client,
            "arn:aws:sns:eu:123:topic",
            "Subject",
            {"key": "val"},
        )
        self.assertEqual(result["MessageId"], "abc123")

    def test_send_to_sns_failure_returns_none(self):
        mock_client = MagicMock()
        mock_client.publish.side_effect = Exception("network error")

        result = send_to_sns(
            _Logger(), mock_client, "arn:aws:sns:eu:123:topic", "Subject", {}
        )
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------
class TestOrganizationsListAccounts(unittest.TestCase):
    def _mock_paginator(self, pages):
        paginator = MagicMock()
        paginator.paginate.return_value = pages
        return paginator

    def test_list_active_accounts(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = self._mock_paginator(
            [
                {
                    "Accounts": [
                        {"Id": "111", "Status": "ACTIVE", "Name": "A"},
                        {"Id": "222", "Status": "SUSPENDED", "Name": "B"},
                        {"Id": "333", "Status": "ACTIVE", "Name": "C"},
                    ]
                }
            ]
        )

        result = organizations_list_accounts(mock_client, _Logger(), only_active=True)
        self.assertEqual(set(result.keys()), {"111", "333"})

    def test_list_all_accounts(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = self._mock_paginator(
            [
                {
                    "Accounts": [
                        {"Id": "111", "Status": "ACTIVE", "Name": "A"},
                        {"Id": "222", "Status": "SUSPENDED", "Name": "B"},
                    ]
                }
            ]
        )

        result = organizations_list_accounts(mock_client, _Logger(), only_active=False)
        self.assertEqual(set(result.keys()), {"111", "222"})


class TestOrganizationsListAccountIds(unittest.TestCase):
    def test_returns_ids(self):
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "Accounts": [
                    {"Id": "a1", "Status": "ACTIVE"},
                    {"Id": "a2", "Status": "ACTIVE"},
                ]
            }
        ]
        mock_client.get_paginator.return_value = paginator

        ids = organizations_list_account_ids(mock_client, _Logger())
        self.assertEqual(set(ids), {"a1", "a2"})


class TestOrganizationsListChildOUs(unittest.TestCase):
    def test_leaf_ou(self):
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Children": []}]
        mock_client.get_paginator.return_value = paginator

        result = organizations_list_child_ous(mock_client, _Logger(), "ou-root")
        self.assertEqual(result, ["ou-root"])

    def test_leaf_ou_without_root(self):
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Children": []}]
        mock_client.get_paginator.return_value = paginator

        result = organizations_list_child_ous(
            mock_client, _Logger(), "ou-root", include_root=False
        )
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# OrganizationsHelper Class Tests
# ---------------------------------------------------------------------------
class TestOrganizationsHelperInitialization(unittest.TestCase):
    def test_initialization_with_client(self):
        """Test OrganizationsHelper initializes with provided client."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {
            "Roots": [{"Id": "r-123", "Name": "root"}]
        }

        helper = OrganizationsHelper(_Logger(), mock_client)

        self.assertEqual(helper.org_id, "o-123")
        self.assertIn("r-123", helper.roots)

    def test_initialization_without_client(self):
        """Test OrganizationsHelper creates default client if not provided."""
        with patch("acai.aws_helper.organizations.boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            mock_client.describe_organization.return_value = {
                "Organization": {"Id": "o-456"}
            }
            mock_client.list_roots.return_value = {"Roots": []}

            helper = OrganizationsHelper(_Logger())

            mock_boto.assert_called_once_with("organizations")
            self.assertEqual(helper.org_id, "o-456")


class TestOrganizationsHelperGetOuId(unittest.TestCase):
    def test_get_ou_id_success(self):
        """Test get_ou_id returns OU ID for an account."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}
        mock_client.list_parents.return_value = {
            "Parents": [{"Id": "ou-abc", "Type": "ORGANIZATIONAL_UNIT"}]
        }

        helper = OrganizationsHelper(_Logger(), mock_client)
        result = helper.get_ou_id("acc-123")

        self.assertEqual(result, "ou-abc")

    def test_get_ou_id_cached(self):
        """Test get_ou_id uses cache on second call."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}
        mock_client.list_parents.return_value = {
            "Parents": [{"Id": "ou-abc", "Type": "ORGANIZATIONAL_UNIT"}]
        }

        helper = OrganizationsHelper(_Logger(), mock_client)

        # First call
        result1 = helper.get_ou_id("acc-123")
        # Second call - should use cache
        result2 = helper.get_ou_id("acc-123")

        self.assertEqual(result1, "ou-abc")
        self.assertEqual(result2, "ou-abc")
        # list_parents should only be called once
        mock_client.list_parents.assert_called_once()

    def test_get_ou_id_no_parents(self):
        """Test get_ou_id returns None when no parents found."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}
        mock_client.list_parents.return_value = {"Parents": []}

        helper = OrganizationsHelper(_Logger(), mock_client)
        result = helper.get_ou_id("acc-123")

        self.assertIsNone(result)


class TestOrganizationsHelperGetTags(unittest.TestCase):
    def test_get_tags_success(self):
        """Test get_tags returns tags for a resource."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}

        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "Tags": [
                    {"Key": "Environment", "Value": "prod"},
                    {"Key": "Owner", "Value": "team-a"},
                ]
            }
        ]
        mock_client.get_paginator.return_value = paginator

        helper = OrganizationsHelper(_Logger(), mock_client)
        result = helper.get_tags("ou-123")

        self.assertEqual(result, {"Environment": "prod", "Owner": "team-a"})

    def test_get_tags_cached(self):
        """Test get_tags uses cache on second call via _get_tags."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}

        paginator = MagicMock()
        paginator.paginate.return_value = [{"Tags": [{"Key": "Name", "Value": "prod"}]}]
        mock_client.get_paginator.return_value = paginator

        helper = OrganizationsHelper(_Logger(), mock_client)

        # First call via private method
        result1 = helper._get_tags("ou-123")
        # Second call - should use cache
        result2 = helper._get_tags("ou-123")

        self.assertEqual(result1, {"Name": "prod"})
        self.assertEqual(result2, {"Name": "prod"})
        # get_paginator should only be called once for cached method
        mock_client.get_paginator.assert_called_once()

    def test_get_tags_empty(self):
        """Test get_tags returns empty dict when no tags."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}

        paginator = MagicMock()
        paginator.paginate.return_value = [{"Tags": []}]
        mock_client.get_paginator.return_value = paginator

        helper = OrganizationsHelper(_Logger(), mock_client)
        result = helper.get_tags("ou-123")

        self.assertEqual(result, {})


class TestOrganizationsHelperOUPaths(unittest.TestCase):
    def _setup_helper_with_hierarchy(self):
        """Create helper with a mock organizational hierarchy.

        Structure:
            Root (r-123)
              ├─ prod (ou-prod)
              │   └─ security (ou-sec)
              │       └─ acc-sec-1
              └─ dev (ou-dev)
                  └─ acc-dev-1
        """
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}

        # Mock list_parents for accounts and OUs
        parents_map = {
            "acc-sec-1": {"Parents": [{"Id": "ou-sec", "Type": "ORGANIZATIONAL_UNIT"}]},
            "ou-sec": {"Parents": [{"Id": "ou-prod", "Type": "ORGANIZATIONAL_UNIT"}]},
            "ou-prod": {"Parents": [{"Id": "r-123", "Type": "ROOT"}]},
            "acc-dev-1": {"Parents": [{"Id": "ou-dev", "Type": "ORGANIZATIONAL_UNIT"}]},
            "ou-dev": {"Parents": [{"Id": "r-123", "Type": "ROOT"}]},
        }

        def list_parents_side_effect(ChildId):
            return parents_map.get(ChildId, {"Parents": []})

        mock_client.list_parents.side_effect = list_parents_side_effect

        # Mock describe_organizational_unit
        ou_names = {
            "ou-prod": "prod",
            "ou-sec": "security",
            "ou-dev": "dev",
        }

        def describe_ou_side_effect(OrganizationalUnitId):
            name = ou_names.get(OrganizationalUnitId, "")
            return {"OrganizationalUnit": {"Name": name}}

        mock_client.describe_organizational_unit.side_effect = describe_ou_side_effect

        return OrganizationsHelper(_Logger(), mock_client)

    def test_get_ou_id_with_path_single_level(self):
        """Test OU path with single level: /o-123/r-123/ou-dev/"""
        helper = self._setup_helper_with_hierarchy()
        ou_id, path = helper._get_ou_id_with_path("acc-dev-1")

        self.assertEqual(ou_id, "ou-dev")
        self.assertEqual(path, "/o-123/r-123/ou-dev/")

    def test_get_ou_id_with_path_nested(self):
        """Test OU path with nested levels: /o-123/r-123/ou-prod/ou-sec/"""
        helper = self._setup_helper_with_hierarchy()
        ou_id, path = helper._get_ou_id_with_path("acc-sec-1")

        self.assertEqual(ou_id, "ou-sec")
        self.assertEqual(path, "/o-123/r-123/ou-prod/ou-sec/")

    def test_get_ou_name_with_path_single_level(self):
        """Test OU name path with single level: /root/dev/"""
        helper = self._setup_helper_with_hierarchy()
        ou_name, path = helper._get_ou_name_with_path("acc-dev-1")

        self.assertEqual(ou_name, "dev")
        self.assertEqual(path, "/root/dev/")

    def test_get_ou_name_with_path_nested(self):
        """Test OU name path with nested levels: /root/prod/security/"""
        helper = self._setup_helper_with_hierarchy()
        ou_name, path = helper._get_ou_name_with_path("acc-sec-1")

        self.assertEqual(ou_name, "security")
        self.assertEqual(path, "/root/prod/security/")

    def test_ou_path_caching(self):
        """Test OU path results are cached."""
        helper = self._setup_helper_with_hierarchy()

        # First call
        ou_id1, path1 = helper._get_ou_id_with_path("acc-dev-1")
        # Second call - should use cache
        ou_id2, path2 = helper._get_ou_id_with_path("acc-dev-1")

        self.assertEqual(ou_id1, ou_id2)
        self.assertEqual(path1, path2)
        self.assertIn("ou-dev", helper.ou_id_with_path_cache)


class TestOrganizationsHelperGetMemberAccountContext(unittest.TestCase):
    def _setup_helper_with_context(self):
        """Create helper with full account context mocking."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}

        # Mock describe_account
        mock_client.describe_account.return_value = {
            "Account": {
                "Id": "123456789012",
                "Name": "prod-database",
                "Status": "ACTIVE",
            }
        }

        # Mock list_parents
        mock_client.list_parents.side_effect = lambda ChildId: (
            {"Parents": [{"Id": "ou-prod", "Type": "ORGANIZATIONAL_UNIT"}]}
            if ChildId == "123456789012"
            else {"Parents": [{"Id": "r-123", "Type": "ROOT"}]}
        )

        # Mock describe_organizational_unit
        mock_client.describe_organizational_unit.return_value = {
            "OrganizationalUnit": {"Name": "prod"}
        }

        # Mock tags
        paginator = MagicMock()
        paginator.paginate.side_effect = lambda ResourceId: [
            (
                {
                    "Tags": [
                        {"Key": "Environment", "Value": "production"},
                        {"Key": "CostCenter", "Value": "12345"},
                    ]
                }
                if ResourceId == "123456789012"
                else {"Tags": [{"Key": "Purpose", "Value": "Production OU"}]}
            )
        ]
        mock_client.get_paginator.return_value = paginator

        return OrganizationsHelper(_Logger(), mock_client)

    def test_get_member_account_context_success(self):
        """Test get_member_account_context returns complete account info."""
        helper = self._setup_helper_with_context()
        context = helper.get_member_account_context("123456789012")

        self.assertIsNotNone(context)
        self.assertEqual(context["accountId"], "123456789012")
        self.assertEqual(context["accountName"], "prod-database")
        self.assertEqual(context["accountStatus"], "ACTIVE")
        self.assertEqual(context["ouId"], "ou-prod")
        self.assertIn("ouIdWithPath", context)
        self.assertIn("ouNameWithPath", context)
        self.assertIn("accountTags", context)
        self.assertIn("ouTags", context)

    def test_get_member_account_context_tags(self):
        """Test account context includes tags."""
        helper = self._setup_helper_with_context()
        context = helper.get_member_account_context("123456789012")

        self.assertEqual(
            context["accountTags"],
            {"Environment": "production", "CostCenter": "12345"},
        )
        self.assertEqual(context["ouTags"], {"Purpose": "Production OU"})

    def test_get_member_account_context_not_found(self):
        """Test get_member_account_context returns None for invalid account."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}
        mock_client.describe_account.return_value = {}  # Empty response

        helper = OrganizationsHelper(_Logger(), mock_client)
        context = helper.get_member_account_context("invalid-acccount")

        self.assertIsNone(context)


class TestOrganizationsHelperErrorHandling(unittest.TestCase):
    def test_get_organization_id_error_raises(self):
        """describe_organization failure must surface during construction."""
        mock_client = MagicMock()
        mock_client.describe_organization.side_effect = Exception("API error")
        mock_client.list_roots.return_value = {"Roots": []}

        with self.assertRaises(Exception) as ctx:
            OrganizationsHelper(_Logger(), mock_client)
        self.assertIn("API error", str(ctx.exception))

    def test_get_tags_error_raises(self):
        """get_tags must propagate AWS errors instead of returning {}."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}
        helper = OrganizationsHelper(_Logger(), mock_client)
        # Configure paginator to fail only after construction succeeded
        mock_client.get_paginator.side_effect = Exception("API error")

        with self.assertRaises(Exception) as ctx:
            helper.get_tags("ou-123")
        self.assertIn("API error", str(ctx.exception))

    def test_describe_account_error_raises(self):
        """_describe_account must propagate AWS errors instead of returning {}."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}
        mock_client.describe_account.side_effect = Exception("Account not found")

        helper = OrganizationsHelper(_Logger(), mock_client)
        with self.assertRaises(Exception) as ctx:
            helper._describe_account("invalid")
        self.assertIn("Account not found", str(ctx.exception))


class TestOrganizationsBackwardCompatibility(unittest.TestCase):
    def test_organizations_get_member_account_context_wrapper(self):
        """Test wrapper function for get_member_account_context."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}
        mock_client.describe_account.return_value = {
            "Account": {"Id": "123", "Name": "test", "Status": "ACTIVE"}
        }
        mock_client.list_parents.return_value = {
            "Parents": [{"Id": "r-123", "Type": "ROOT"}]
        }
        mock_client.get_paginator.return_value.paginate.return_value = [{"Tags": []}]

        context = organizations_get_member_account_context(
            mock_client, _Logger(), "123"
        )

        self.assertIsNotNone(context)
        self.assertEqual(context["accountId"], "123")

    def test_organizations_get_ou_id_wrapper(self):
        """Test wrapper function for get_ou_id."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}
        mock_client.list_parents.return_value = {
            "Parents": [{"Id": "ou-123", "Type": "ORGANIZATIONAL_UNIT"}]
        }

        result = organizations_get_ou_id(mock_client, _Logger(), "acc-123")

        self.assertEqual(result, "ou-123")

    def test_organizations_get_tags_wrapper(self):
        """Test wrapper function for get_tags."""
        mock_client = MagicMock()
        mock_client.describe_organization.return_value = {
            "Organization": {"Id": "o-123"}
        }
        mock_client.list_roots.return_value = {"Roots": [{"Id": "r-123"}]}

        paginator = MagicMock()
        paginator.paginate.return_value = [{"Tags": [{"Key": "Name", "Value": "prod"}]}]
        mock_client.get_paginator.return_value = paginator

        result = organizations_get_tags(mock_client, _Logger(), "ou-123")

        self.assertEqual(result, {"Name": "prod"})


if __name__ == "__main__":
    unittest.main()
