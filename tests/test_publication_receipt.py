import hashlib
import unittest
import urllib.error
from unittest.mock import MagicMock, Mock

from scripts.publication_receipt import MEDIA_TYPES, PublicationError, Registry, make_receipt, push_digest


SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
REPO = "TheAnh-05-UIT/gitops-platform-workload-api"
ENV = {
    "GITHUB_REPOSITORY": REPO, "GITHUB_SHA": SHA, "GITHUB_RUN_ID": "42",
    "GITHUB_RUN_ATTEMPT": "1", "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "push",
    "GITHUB_WORKFLOW_REF": f"{REPO}/.github/workflows/ci.yml@refs/heads/main",
}


class PublicationReceiptTests(unittest.TestCase):
    def test_verified_receipt_has_immutable_workflow_identity(self):
        output = f"{SHA}: digest: {DIGEST} size: 123\n"
        self.assertEqual(push_digest(output, SHA), DIGEST)
        receipt = make_receipt(ENV, DIGEST, DIGEST)
        self.assertEqual(receipt["sha"], SHA)
        self.assertEqual(receipt["run_id"], 42)
        self.assertEqual(receipt["run_attempt"], 1)
        self.assertEqual(receipt["digest"], DIGEST)
        self.assertEqual(receipt["workflow"], ".github/workflows/ci.yml")

    def test_failed_missing_or_mismatched_push_is_rejected(self):
        with self.assertRaises(PublicationError):
            push_digest("failed to push", SHA)
        with self.assertRaises(PublicationError):
            make_receipt(ENV, DIGEST, "sha256:" + "c" * 64)

    def test_untrusted_workflow_is_rejected(self):
        with self.assertRaises(PublicationError):
            make_receipt(ENV | {"GITHUB_REF": "refs/heads/topic"}, DIGEST, DIGEST)

    def test_registry_checks_content_bytes_and_distinguishes_missing_from_auth_failure(self):
        def response(data, headers=None):
            item = MagicMock(headers=headers or {})
            item.__enter__.return_value = item
            item.read.return_value = data
            return item

        raw = b'{"schemaVersion":2}'
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        metadata = {"Docker-Content-Digest": digest, "Content-Type": MEDIA_TYPES[0]}
        missing = urllib.error.HTTPError("https://ghcr.io", 404, "missing", {}, None)
        denied = urllib.error.HTTPError("https://ghcr.io", 401, "denied", {}, None)
        opener = Mock(side_effect=[
            response(b'{"token":"synthetic"}'), response(raw, metadata),
            response(raw + b"tampered", metadata), missing, denied,
        ])
        registry = Registry("fixture", "synthetic", opener=opener)
        self.assertEqual(registry.manifest(SHA), (digest, MEDIA_TYPES[0]))
        with self.assertRaises(PublicationError):
            registry.manifest(SHA)
        self.assertIsNone(registry.manifest(SHA))
        with self.assertRaisesRegex(PublicationError, "HTTP 401"):
            registry.manifest(SHA)
        self.assertTrue(all(call.args[0].get_method() == "GET" for call in opener.call_args_list))
