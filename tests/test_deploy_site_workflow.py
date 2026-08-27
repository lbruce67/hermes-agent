"""Tests for .github/workflows/deploy-site.yml GitHub Pages deployment.

deploy-pages v5.0.0 runs on Node.js 24.x inside the action (not the workflow's
setup-node pin). GitHub-hosted ubuntu-latest runners satisfy that runtime.
upload-pages-artifact v5.0.0 pairs with deploy-pages v5.0.0 for the Pages
artifact format consumed by the deployment API.

These tests pin:
  - SHA-pinned action versions (supply-chain policy)
  - the deployment security boundary (permissions + environment)
  - the upload-before-deploy step order required by the Pages API
"""

from __future__ import annotations

import pathlib
import re

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "deploy-site.yml"

# Cross-referenced against upstream release tags at review time:
#   actions/deploy-pages@v5.0.0
#   actions/upload-pages-artifact@v5.0.0
DEPLOY_PAGES_V5_SHA = "cd2ce8fcbc39b97be8ca5fce6e763baed58fa128"
UPLOAD_PAGES_ARTIFACT_V5_SHA = "fc324d3547104276b827a68afc52ff2a11cc49c9"

_SHA_PIN = re.compile(
    r"uses:\s+actions/(?P<action>deploy-pages|upload-pages-artifact)"
    r"@(?P<sha>[0-9a-f]{40})\s+#\s+v(?P<version>\d+\.\d+\.\d+)"
)


def _workflow_text() -> str:
    assert WORKFLOW_PATH.exists(), f"workflow missing: {WORKFLOW_PATH}"
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _parsed_workflow() -> dict:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    content = _workflow_text()
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        pytest.fail(f"deploy-site.yml is not valid YAML: {exc}")
    assert isinstance(parsed, dict)
    return parsed


class TestDeploySiteWorkflow:
    def test_workflow_yaml_is_valid(self):
        parsed = _parsed_workflow()
        assert "jobs" in parsed
        assert "deploy-docs" in parsed["jobs"]

    def test_pages_actions_pinned_to_v5_shas(self):
        """Both Pages actions must be full-SHA pinned at v5.0.0."""
        text = _workflow_text()
        pins = {m.group("action"): m.groupdict() for m in _SHA_PIN.finditer(text)}
        assert pins.get("deploy-pages") == {
            "action": "deploy-pages",
            "sha": DEPLOY_PAGES_V5_SHA,
            "version": "5.0.0",
        }
        assert pins.get("upload-pages-artifact") == {
            "action": "upload-pages-artifact",
            "sha": UPLOAD_PAGES_ARTIFACT_V5_SHA,
            "version": "5.0.0",
        }

    def test_pages_permissions_security_boundary(self):
        """Pages deploy needs OIDC + pages write; must not broaden contents."""
        parsed = _parsed_workflow()
        perms = parsed.get("permissions") or {}
        assert perms.get("contents") == "read"
        assert perms.get("actions") == "read"
        assert perms.get("pages") == "write"
        assert perms.get("id-token") == "write"
        assert perms.get("contents") != "write"

    def test_deploy_docs_uses_github_pages_environment(self):
        parsed = _parsed_workflow()
        env = parsed["jobs"]["deploy-docs"].get("environment") or {}
        assert env.get("name") == "github-pages"

    def test_deploy_docs_runs_on_ubuntu_latest(self):
        """ubuntu-latest provides the Node 24.x runtime deploy-pages v5 needs."""
        parsed = _parsed_workflow()
        assert parsed["jobs"]["deploy-docs"]["runs-on"] == "ubuntu-latest"

    def test_upload_artifact_before_deploy_pages(self):
        """deploy-pages must consume the artifact uploaded in the prior step."""
        text = _workflow_text()
        upload_idx = text.find("actions/upload-pages-artifact@")
        deploy_idx = text.find("actions/deploy-pages@")
        assert upload_idx != -1 and deploy_idx != -1
        assert upload_idx < deploy_idx

    def test_deploy_pages_step_has_id_for_page_url(self):
        parsed = _parsed_workflow()
        steps = parsed["jobs"]["deploy-docs"]["steps"]
        deploy_steps = [
            s for s in steps
            if isinstance(s, dict)
            and "uses" in s
            and "deploy-pages@" in str(s["uses"])
        ]
        assert len(deploy_steps) == 1
        assert deploy_steps[0].get("id") == "deploy"

    def test_deploy_pages_only_used_in_deploy_site_workflow(self):
        """deploy-pages bumps must stay scoped to the Pages deploy workflow."""
        workflows_dir = REPO_ROOT / ".github" / "workflows"
        offenders = []
        for path in workflows_dir.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            if "actions/deploy-pages@" in text and path.name != WORKFLOW_PATH.name:
                offenders.append(path.name)
        assert not offenders, (
            f"deploy-pages also referenced in: {offenders} — "
            "keep Pages action pins consistent across every consumer."
        )
