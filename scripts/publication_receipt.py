"""Verify the GHCR manifest and record the successful push identity."""

import argparse
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = "theanh-05-uit/gitops-platform-workload-api"
WORKFLOW = ".github/workflows/ci.yml"
MEDIA_TYPES = (
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)


class PublicationError(ValueError):
    pass


def source(environ):
    repo = environ.get("GITHUB_REPOSITORY", "").lower()
    sha = environ.get("GITHUB_SHA", "")
    if (
        repo != REPOSITORY
        or not re.fullmatch(r"[0-9a-f]{40}", sha)
        or environ.get("GITHUB_REF") != "refs/heads/main"
        or environ.get("GITHUB_EVENT_NAME") != "push"
        or environ.get("GITHUB_WORKFLOW_REF", "").lower() != f"{repo}/{WORKFLOW}@refs/heads/main"
    ):
        raise PublicationError("Receipt is restricted to the trusted main publication workflow")
    return sha


def push_digest(output, sha):
    pattern = rf"^{re.escape(sha)}: digest: (sha256:[0-9a-f]{{64}}) size: [0-9]+\s*$"
    digests = re.findall(pattern, output, re.MULTILINE)
    if len(digests) != 1:
        raise PublicationError("Expected exactly one digest in successful Docker push output")
    return digests[0]


def make_receipt(environ, pushed, observed):
    sha = source(environ)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", pushed) or pushed != observed:
        raise PublicationError("Pushed digest and observed manifest do not agree")
    run_id = int(environ.get("GITHUB_RUN_ID", "0"))
    attempt = int(environ.get("GITHUB_RUN_ATTEMPT", "0"))
    if min(run_id, attempt) < 1:
        raise PublicationError("Missing trusted workflow run identity")
    return {
        "version": 1, "repository": REPOSITORY, "workflow": WORKFLOW,
        "sha": sha, "run_id": run_id, "run_attempt": attempt,
        "image": f"ghcr.io/{REPOSITORY}:{sha}", "digest": observed,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Registry:
    def __init__(self, actor, credential, opener=None):
        if not actor or not credential:
            raise PublicationError("Missing GHCR publisher authentication")
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open
        basic = base64.b64encode(f"{actor}:{credential}".encode()).decode()
        query = urllib.parse.urlencode({"service": "ghcr.io", "scope": f"repository:{REPOSITORY}:pull"})
        data = self.read(f"/token?{query}", f"Basic {basic}")[0]
        token = json.loads(data).get("token")
        if not isinstance(token, str) or not token:
            raise PublicationError("GHCR did not return a scoped registry token")
        self.authorization = f"Bearer {token}"

    def read(self, path, authorization, *, missing=False):
        request = urllib.request.Request(
            f"https://ghcr.io{path}",
            headers={"Authorization": authorization, "Accept": ", ".join(MEDIA_TYPES)},
        )
        try:
            with self.opener(request, timeout=15) as response:
                body = response.read(4 * 1024 * 1024 + 1)
                if len(body) > 4 * 1024 * 1024:
                    raise PublicationError("Registry response exceeds publication limit")
                return body, response.headers
        except urllib.error.HTTPError as error:
            error.close()
            if missing and error.code == 404:
                return None
            raise PublicationError(f"GHCR request failed (HTTP {error.code})") from None
        except OSError:
            raise PublicationError("GHCR request failed or timed out") from None

    def manifest(self, reference):
        result = self.read(f"/v2/{REPOSITORY}/manifests/{reference}", self.authorization, missing=True)
        if result is None:
            return None
        body, headers = result
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
        media_type = headers.get("Content-Type", "").split(";", 1)[0]
        if headers.get("Docker-Content-Digest") != digest or media_type not in MEDIA_TYPES:
            raise PublicationError("Registry manifest digest or media type is invalid")
        return digest, media_type


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("check-absent")
    record = subparsers.add_parser("record")
    record.add_argument("--push-log", required=True, type=Path)
    record.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        sha = source(os.environ)
        registry = Registry(os.environ.get("GITHUB_ACTOR"), os.environ.get("GHCR_TOKEN"))
        manifest = registry.manifest(sha)
        if args.action == "check-absent":
            if manifest is not None:
                raise PublicationError("Source tag already exists; retain its original publication receipt")
            print("Source tag is absent")
            return 0
        pushed = push_digest(args.push_log.read_text(encoding="utf-8"), sha)
        if manifest is None or registry.manifest(pushed) != manifest:
            raise PublicationError("Published manifest is unavailable by tag or digest")
        observed, media_type = manifest
        receipt = make_receipt(os.environ, pushed, observed) | {"media_type": media_type}
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    except PublicationError as error:
        parser.exit(1, f"Publication receipt blocked: {error}\n")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "Publication receipt blocked: invalid or inaccessible evidence\n")
    print("Verified and recorded the GHCR publication receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
