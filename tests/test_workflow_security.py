import re
import unittest
from pathlib import Path

import yaml


class WorkflowSecurityTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.load(Path(".github/workflows/ci.yml").read_bytes(), Loader=yaml.BaseLoader)
        self.jobs = self.workflow["jobs"]

    def test_only_publisher_can_write_packages_and_only_on_protected_path(self):
        writers = [name for name, job in self.jobs.items()
                   if job.get("permissions", {}).get("packages") == "write"]
        self.assertEqual(writers, ["publish"])
        self.assertNotIn("packages", self.workflow["permissions"])
        publish = self.jobs["publish"]
        self.assertIn("github.event_name == 'push'", publish["if"])
        self.assertIn("github.ref == 'refs/heads/main'", publish["if"])
        self.assertIn("github.ref_protected", publish["if"])
        self.assertIn("github.repository == 'TheAnh-05-UIT/gitops-platform-workload-api'", publish["if"])
        self.assertEqual(self.workflow["on"]["push"]["branches"], ["main"])
        self.assertEqual(publish["environment"], "workload-publication")
        self.assertEqual(next(step["env"]["GHCR_TOKEN"] for step in publish["steps"]
                              if step.get("name") == "Publish image to GHCR"),
                         "${{ secrets.GHCR_PUBLISH_TOKEN }}")
        for name, job in self.jobs.items():
            if name != "publish":
                self.assertNotIn("GHCR_TOKEN", str(job))
                self.assertNotIn("GHCR_PUBLISH_TOKEN", str(job))
                self.assertNotIn("docker login", str(job))
        self.assertFalse(any("docker build" in step.get("run", "") for step in publish["steps"]))

    def test_preview_stays_disabled_and_read_only_during_hosted_review(self):
        preview = yaml.load(Path(".github/workflows/promotion-preview.yml").read_bytes(),
                            Loader=yaml.BaseLoader)
        self.assertEqual(set(preview["on"]), {"workflow_dispatch"})
        self.assertEqual(set(preview["permissions"].values()), {"read"})
        self.assertTrue(preview["jobs"]["preview"]["if"].startswith("false &&"))

    def test_failed_or_skipped_scan_cannot_reach_publish(self):
        scan = self.jobs["scan"]
        publish = self.jobs["publish"]
        self.assertEqual(scan["needs"], "build")
        self.assertEqual(set(publish["needs"]), {"build", "scan"})
        self.assertEqual(set(re.split(r"\s*&&\s*", publish["if"])), {
            "false",
            "github.event_name == 'push'",
            "github.ref == 'refs/heads/main'",
            "github.ref_protected",
            "github.repository == 'TheAnh-05-UIT/gitops-platform-workload-api'",
            "needs.build.result == 'success'",
            "needs.scan.result == 'success'",
            "needs.scan.outputs.trivy_outcome == 'success'",
        })
        self.assertEqual(scan["outputs"]["trivy_outcome"], "${{ steps.trivy.outcome }}")
        step = next(step for step in scan["steps"] if step.get("id") == "trivy")
        self.assertNotIn("if", step)
        self.assertNotIn("continue-on-error", step)
        self.assertNotIn("continue-on-error", scan)
        self.assertTrue(re.fullmatch(r"aquasecurity/trivy-action@[0-9a-f]{40}", step["uses"]))
        self.assertEqual(step["with"]["version"], "${{ env.TRIVY_VERSION }}")
        self.assertEqual(self.workflow["env"]["TRIVY_VERSION"], "v0.76.2")
        self.assertEqual(step["with"]["exit-code"], "1")
        self.assertEqual(step["with"]["severity"], "CRITICAL")
        self.assertEqual(step["with"]["scanners"], "vuln")

    def test_scan_and_publish_consume_the_same_artifact_and_check_its_hash(self):
        for name in ("scan", "publish"):
            job = self.jobs[name]
            download = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/download-artifact@"))
            self.assertEqual(download["with"]["artifact-ids"], "${{ needs.build.outputs.artifact_id }}")
            verify = next(s for s in job["steps"] if s.get("name") == "Verify image archive")
            self.assertEqual(verify["env"]["EXPECTED_ARCHIVE_SHA"], "${{ needs.build.outputs.archive_sha }}")
            self.assertIn("sha256sum --check --strict", verify["run"])

    def test_pr_job_installs_app_dependencies_before_running_tests(self):
        commands = [step["run"] for step in self.jobs["validate-pr"]["steps"] if "run" in step]
        suite = next(i for i, command in enumerate(commands) if "-m unittest discover" in command)
        self.assertTrue(any("-m pip install" in command and "-r requirements.txt" in command
                            for command in commands[:suite]))
