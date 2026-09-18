from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.collect_evidence import Check, render_markdown, verify_kubernetes_evidence

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("deploy.sh", "planned_steps=terraform_init,terraform_apply,kubectl_rollout_status"),
        ("rollback.sh", "action=kubectl_rollout_undo"),
        ("failure-drill.sh", "scenario=readiness_failure_then_rollout_undo"),
    ],
)
def test_bash_automation_dry_runs_without_external_runtimes(script: str, expected: str) -> None:
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts" / script), "--dry-run"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    assert completed.returncode == 0, completed.stdout
    assert "dry_run=passed" in completed.stdout
    assert expected in completed.stdout


def test_deploy_rejects_invalid_namespace_before_runtime_access() -> None:
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts" / "deploy.sh"), "--namespace", "INVALID_NAME"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    assert completed.returncode == 2
    assert "invalid Kubernetes namespace" in completed.stdout


def test_drill_evidence_writer_uses_measured_arguments(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "write_drill_evidence.py"),
            "--output-dir",
            str(tmp_path),
            "--namespace",
            "release-lab",
            "--deployment",
            "release-status",
            "--before-revision",
            "3",
            "--after-revision",
            "5",
            "--desired-replicas",
            "2",
            "--ready-during-failure",
            "2",
            "--ready-after-recovery",
            "2",
            "--failure-timeout",
            "20s",
            "--duration-seconds",
            "24",
            "--failed-release",
            "failed-candidate-test",
            "--smoke-executed",
            "true",
            "--rollout-output",
            "timed out waiting for the condition",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    assert completed.returncode == 0, completed.stdout
    report = json.loads((tmp_path / "kubernetes-drill.json").read_text(encoding="utf-8"))
    assert report["failure_observed"] is True
    assert report["rollback_recovered"] is True
    assert report["ready_replicas_during_failure"] == 2
    assert report["ready_replicas_after_recovery"] == 2
    assert report["post_recovery_smoke_executed"] is True


def test_markdown_report_marks_skips_as_boundaries() -> None:
    report = {
        "generated_at": "2026-09-17T00:00:00+00:00",
        "release_id": "test",
        "revision": "abc123",
        "overall_status": "passed",
        "summary": {"passed": 1, "failed": 0, "skipped": 1},
        "checks": [
            Check("python_tests", "test", "passed", detail="12 tests").__dict__,
            Check("kubernetes_runtime", "orchestration", "skipped", detail="no context").__dict__,
        ],
        "claim_boundaries": {
            "docker_executed": False,
            "kubernetes_rollout_executed": False,
            "azure_deployment_executed": False,
            "ci_run_executed": False,
        },
    }

    markdown = render_markdown(report)

    assert "Skipped checks are boundaries, not successes" in markdown
    assert "Kubernetes rollout/failure drill validated in this run: **false**" in markdown


def test_kubernetes_evidence_requires_retained_capacity_and_post_recovery_smoke(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "drill.json"
    evidence.write_text(
        json.dumps(
            {
                "status": "passed",
                "failure_observed": True,
                "rollback_recovered": True,
                "post_recovery_smoke_executed": True,
                "desired_replicas": 2,
                "ready_replicas_during_failure": 2,
                "ready_replicas_after_recovery": 2,
                "duration_seconds": 24,
                "before_revision": "1",
                "after_revision": "3",
            }
        ),
        encoding="utf-8",
    )

    check = verify_kubernetes_evidence(evidence)

    assert check.status == "passed"
    assert check.measurements["ready_during_failure"] == 2


def test_kubernetes_evidence_rejects_missing_smoke_proof(tmp_path: Path) -> None:
    evidence = tmp_path / "drill.json"
    evidence.write_text(
        json.dumps(
            {
                "status": "passed",
                "failure_observed": True,
                "rollback_recovered": True,
                "post_recovery_smoke_executed": False,
                "desired_replicas": 2,
                "ready_replicas_during_failure": 2,
                "ready_replicas_after_recovery": 2,
            }
        ),
        encoding="utf-8",
    )

    check = verify_kubernetes_evidence(evidence)

    assert check.status == "failed"
