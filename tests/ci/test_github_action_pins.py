"""Contract tests for pinned third-party GitHub Actions in CI workflows.

Dependabot bumps action SHAs on a schedule; these tests keep every workflow
reference aligned with the canonical pin in ``.github/action-pins.json`` so
audits do not have to grep five workflow files by hand.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
ACTION_PINS = REPO_ROOT / ".github" / "action-pins.json"

SETUP_UV_USES_RE = re.compile(
    r"^\s*uses:\s+astral-sh/setup-uv@([0-9a-f]{40})\s+#\s*(v[\d.]+)\s*$"
)


def _load_pins() -> dict[str, dict[str, str]]:
    assert ACTION_PINS.is_file(), f"missing canonical pin file: {ACTION_PINS}"
    return json.loads(ACTION_PINS.read_text(encoding="utf-8"))


def _setup_uv_uses_lines() -> list[tuple[Path, int, str, str, str]]:
    """Return (path, line_no, sha, version_comment, raw_line) for each setup-uv use."""
    rows: list[tuple[Path, int, str, str, str]] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for line_no, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = SETUP_UV_USES_RE.match(line)
            if match:
                rows.append(
                    (workflow, line_no, match.group(1), match.group(2), line)
                )
    return rows


def test_setup_uv_pin_manifest_matches_official_release():
    """SHA + version comment must match the audited v8.3.0 release pin."""
    pin = _load_pins()["astral-sh/setup-uv"]
    assert pin["sha"] == "d31148d669074a8d0a63714ba94f3201e7020bc3"
    assert pin["version"] == "v8.3.0"
    assert pin["release_url"].endswith("/releases/tag/v8.3.0")


def test_all_workflows_use_canonical_setup_uv_pin():
    pin = _load_pins()["astral-sh/setup-uv"]
    expected_sha = pin["sha"]
    expected_version = pin["version"]

    rows = _setup_uv_uses_lines()
    assert rows, "expected at least one astral-sh/setup-uv reference in workflows"

    for workflow, line_no, sha, version, raw in rows:
        assert sha == expected_sha, (
            f"{workflow.relative_to(REPO_ROOT)}:{line_no} pins {sha}, "
            f"expected {expected_sha}. Line: {raw!r}"
        )
        assert version == expected_version, (
            f"{workflow.relative_to(REPO_ROOT)}:{line_no} comment {version!r}, "
            f"expected {expected_version!r}. Line: {raw!r}"
        )


def test_setup_uv_referenced_in_expected_workflows():
    """Every workflow that installs uv must use the shared pin."""
    rows = _setup_uv_uses_lines()
    workflow_names = {path.name for path, *_ in rows}
    assert workflow_names == {
        "docker-publish.yml",
        "lint.yml",
        "tests.yml",
        "upload_to_pypi.yml",
        "uv-lockfile-check.yml",
    }
    assert len(rows) == 7


def test_tests_workflow_keeps_uv_cache_inputs():
    """setup-uv v8.x cache inputs used by tests.yml must stay configured."""
    content = (WORKFLOWS_DIR / "tests.yml").read_text(encoding="utf-8")
    assert "enable-cache: true" in content
    assert "cache-dependency-glob:" in content
    assert "pyproject.toml" in content
    assert "uv.lock" in content


def test_lint_workflow_still_uses_uv_tool_install():
    """lint.yml installs ruff/ty via uv tool — must remain after setup-uv bumps."""
    content = (WORKFLOWS_DIR / "lint.yml").read_text(encoding="utf-8")
    assert "uv tool install ruff" in content
    assert "uv tool install ty" in content


def test_tests_workflow_still_uses_uv_python_install_and_sync():
    content = (WORKFLOWS_DIR / "tests.yml").read_text(encoding="utf-8")
    assert "uv python install 3.11" in content
    assert "uv sync --locked" in content
    assert "uv cache prune --ci" in content
