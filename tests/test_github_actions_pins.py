"""Guard GitHub Actions checkout pins and workflow trigger safety.

actions/checkout v7.0.1 (commit 3d3c42e5aac5ba805825da76410c181273ba90b1) is
pinned by full SHA across all workflows per CONTRIBUTING.md supply-chain policy.
The SHA matches the official v7.0.1 release tag:
https://github.com/actions/checkout/releases/tag/v7.0.1

v7 breaking changes (ESM module, fork-PR blocking on pull_request_target /
workflow_run) do not affect this repo: no workflow uses those triggers, and all
checkout steps run on push / pull_request / schedule / workflow_dispatch only.
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Official actions/checkout v7.0.1 release commit (verified against the tag above).
CHECKOUT_V7_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
CHECKOUT_V7_TAG = "v7.0.1"

# Full SHA (40 hex) + inline version comment — CONTRIBUTING.md required format.
CHECKOUT_PIN_RE = re.compile(
    rf"actions/checkout@{CHECKOUT_V7_SHA}\s+#\s+{re.escape(CHECKOUT_V7_TAG)}"
)

# Triggers where checkout v7's fork-PR hardening would block untrusted refs.
UNSAFE_WORKFLOW_TRIGGERS = frozenset({"pull_request_target", "workflow_run"})


def _workflow_files() -> list[pathlib.Path]:
    assert WORKFLOWS_DIR.is_dir(), f"Missing workflows dir: {WORKFLOWS_DIR}"
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


def _load_workflow_on_block(content: str) -> str:
    """Return the raw ``on:`` block (through first top-level ``jobs:``)."""
    lines = content.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "on:")
    end = next(
        (i for i, line in enumerate(lines[start + 1 :], start + 1) if line.startswith("jobs:")),
        len(lines),
    )
    return "\n".join(lines[start:end])


class TestCheckoutPin:
    def test_official_v7_sha_constant_is_full_length(self):
        assert len(CHECKOUT_V7_SHA) == 40
        assert re.fullmatch(r"[0-9a-f]{40}", CHECKOUT_V7_SHA)

    @pytest.mark.parametrize("workflow_path", _workflow_files(), ids=lambda p: p.name)
    def test_checkout_uses_pinned_v7_sha_with_comment(self, workflow_path: pathlib.Path):
        content = workflow_path.read_text(encoding="utf-8")
        checkout_lines = [
            line.strip()
            for line in content.splitlines()
            if "actions/checkout@" in line
        ]
        if not checkout_lines:
            pytest.skip(f"{workflow_path.name} does not use actions/checkout")

        bad = [line for line in checkout_lines if not CHECKOUT_PIN_RE.search(line)]
        assert not bad, (
            f"{workflow_path.name}: every actions/checkout pin must be "
            f"actions/checkout@{CHECKOUT_V7_SHA}  # {CHECKOUT_V7_TAG}. "
            f"Offending line(s): {bad!r}"
        )

    def test_all_workflows_using_checkout_share_one_sha(self):
        seen: set[str] = set()
        for path in _workflow_files():
            for match in re.finditer(r"actions/checkout@([0-9a-f]{40})", path.read_text(encoding="utf-8")):
                seen.add(match.group(1))
        assert seen == {CHECKOUT_V7_SHA}, (
            "Multiple checkout SHAs detected — bump all workflows together: "
            f"expected only {CHECKOUT_V7_SHA}, found {sorted(seen)}"
        )


class TestWorkflowTriggerSafety:
    @pytest.mark.parametrize("workflow_path", _workflow_files(), ids=lambda p: p.name)
    def test_no_unsafe_triggers_for_checkout_v7(self, workflow_path: pathlib.Path):
        """checkout v7 blocks fork PR refs on pull_request_target / workflow_run."""
        on_block = _load_workflow_on_block(workflow_path.read_text(encoding="utf-8"))
        hits = sorted(
            trigger
            for trigger in UNSAFE_WORKFLOW_TRIGGERS
            if re.search(rf"^\s*{re.escape(trigger)}\s*:", on_block, re.MULTILINE)
        )
        assert not hits, (
            f"{workflow_path.name} uses {hits} — incompatible with checkout v7 "
            "fork-PR blocking unless refs are explicitly trusted."
        )

    def test_repo_has_expected_workflow_count(self):
        """Sanity: catch accidental workflow dir drift during pin bumps."""
        count = len(_workflow_files())
        assert count >= 15, f"Expected at least 15 workflow files, found {count}"
