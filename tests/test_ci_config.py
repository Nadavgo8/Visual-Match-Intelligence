"""The CI workflow keeps the properties the quality gates rely on."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
LOCK = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")


def test_required_check_jobs_exist():
    jobs = set(re.findall(r"^  ([a-z-]+):\n    (?:needs|runs-on)", WORKFLOW, re.M))
    assert jobs == {"python-tests", "coverage-gate", "web-tests", "static-checks"}


def test_runs_on_prs_and_pushes_to_main_without_path_filters():
    assert "pull_request:\n    branches: [main]" in WORKFLOW
    assert "push:\n    branches: [main]" in WORKFLOW
    assert "paths" not in WORKFLOW  # a docs-only PR must not leave a required check pending


def test_permissions_are_read_only_and_every_job_has_a_timeout():
    assert "permissions:\n  contents: read" in WORKFLOW
    assert "write" not in WORKFLOW
    assert WORKFLOW.count("timeout-minutes:") == 4


def test_actions_are_pinned_to_full_commit_shas():
    uses = re.findall(r"uses: (\S+)", WORKFLOW)
    assert uses
    assert all(re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", u) for u in uses), uses


def test_no_check_is_allowed_to_fail_silently():
    assert "continue-on-error" not in WORKFLOW
    assert "|| true" not in WORKFLOW.replace('grep -c "::" || true', "")  # only the count may be zero, then checked


def test_tests_run_strict_and_offline():
    assert "--strict-markers --strict-config -p no:cacheprovider -W error" in WORKFLOW
    assert 'VMI_OFFLINE: "1"' in WORKFLOW


def test_lock_pins_every_package_and_scopes_windows_only_ones():
    lines = [ln for ln in LOCK.splitlines() if ln and not ln.startswith("#")]
    assert lines and all("==" in ln for ln in lines)
    pywin = [ln for ln in lines if ln.lower().startswith("pywin32")]
    assert all('sys_platform == "win32"' in ln for ln in pywin)
    for tool in ("pytest==", "pytest-cov==", "ruff==", "jsonschema==", "agent-framework=="):
        assert any(ln.lower().startswith(tool) for ln in lines), tool


ROOT_FILES = Path(__file__).resolve().parents[1]


def test_container_build_excludes_local_environments_and_installs_the_lock():
    ignore = (ROOT_FILES / ".dockerignore").read_text(encoding="utf-8").split()
    assert {".venv", "out", ".git", "tests"} <= set(ignore)  # --source . must not upload the 900 MB venv
    docker = (ROOT_FILES / "Dockerfile").read_text(encoding="utf-8")
    assert "requirements-lock.txt" in docker and "-r requirements.txt" not in docker


def test_deploy_script_refuses_subscriptions_that_could_bill_and_grants_real_roles():
    script = (ROOT_FILES / "infra" / "deploy.sh").read_text(encoding="utf-8")
    guard = script.index('if [ "$LIMIT" != "On" ]')
    assert guard < script.index("az group create") and guard < script.index("az containerapp up")
    assert '"Cognitive Services User"' in script and '"Azure AI Developer"' in script
    assert "Azure AI User" not in script  # that role name doesn't exist
