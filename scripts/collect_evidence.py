#!/usr/bin/env python3
"""Run local quality gates and generate command-backed JSON/Markdown evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "evidence"
MAX_OUTPUT_CHARS = 12_000
OPERATIONAL_ENDPOINTS = ("/health/live", "/health/ready", "/version", "/metrics")
POWERSHELL_IMAGE = (
    "mcr.microsoft.com/powershell@"
    "sha256:a6beeddb2fcf45547c9099fba091ce231e51aa374fe62ecc182f7c28b69a6cbf"
)


@dataclass
class Check:
    name: str
    category: str
    status: str
    command: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    detail: str = ""
    output_tail: str = ""
    measurements: dict[str, Any] = field(default_factory=dict)


def run_command(
    name: str,
    category: str,
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> Check:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        return Check(
            name=name,
            category=category,
            status="failed",
            command=command,
            duration_seconds=round(time.monotonic() - started, 3),
            detail=f"command not found: {exc.filename}",
        )

    output = completed.stdout or ""
    return Check(
        name=name,
        category=category,
        status="passed" if completed.returncode == 0 else "failed",
        command=command,
        duration_seconds=round(time.monotonic() - started, 3),
        detail=f"exit code {completed.returncode}",
        output_tail=output[-MAX_OUTPUT_CHARS:].strip(),
    )


def skipped(name: str, category: str, detail: str) -> Check:
    return Check(name=name, category=category, status="skipped", detail=detail)


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


def git_revision() -> str:
    root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if root_result.returncode != 0:
        return "uncommitted-local-workspace"
    if Path(root_result.stdout.strip()).resolve() != ROOT:
        return "uncommitted-local-workspace"
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return result.stdout.strip() if result.returncode == 0 else "uncommitted-local-workspace"


def repository_contract_check() -> Check:
    required = [
        "Dockerfile",
        "compose.yaml",
        "app/main.py",
        "app/settings.py",
        "tests/test_health.py",
        "infra/kubernetes/main.tf",
        "infra/azure/README.md",
        "scripts/validate.sh",
        "scripts/validate.ps1",
        ".github/workflows/ci.yml",
        "README.md",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    if missing:
        return Check(
            name="repository_contract",
            category="static",
            status="failed",
            detail="missing required files",
            measurements={"missing": missing},
        )
    return Check(
        name="repository_contract",
        category="static",
        status="passed",
        detail=f"all {len(required)} required files present",
        measurements={"required_files_checked": len(required)},
    )


def run_python_checks(output_dir: Path) -> list[Check]:
    checks: list[Check] = []
    junit_path = output_dir / "pytest.xml"
    test_check = run_command(
        "python_tests",
        "test",
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={junit_path}"],
    )
    match = re.search(r"(\d+) passed", test_check.output_tail)
    if match:
        test_check.measurements["tests_passed"] = int(match.group(1))
    checks.append(test_check)

    checks.append(
        run_command(
            "python_compile",
            "static",
            [sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"],
        )
    )

    if importlib.util.find_spec("ruff"):
        checks.append(
            run_command(
                "ruff",
                "static",
                [sys.executable, "-m", "ruff", "check", "app", "scripts", "tests"],
            )
        )
    else:
        checks.append(skipped("ruff", "static", "ruff is not installed in this Python environment"))
    return checks


def run_script_checks(require_powershell: bool) -> list[Check]:
    bash_scripts = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "scripts").glob("*.sh"))
    checks = [
        run_command("bash_syntax", "automation", ["bash", "-n", *bash_scripts])
        if bash_scripts
        else Check("bash_syntax", "automation", "failed", detail="no Bash scripts found")
    ]

    ps_scripts = sorted((ROOT / "scripts").glob("*.ps1"))
    if command_available("pwsh"):
        expression = "; ".join(
            f"[void][scriptblock]::Create((Get-Content -Raw '{path.as_posix()}'))"
            for path in ps_scripts
        )
        checks.append(
            run_command(
                "powershell_parse",
                "automation",
                ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", expression],
            )
        )
    elif command_available("docker") and subprocess.run(
        ["docker", "image", "inspect", POWERSHELL_IMAGE],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0:
        container_expression = "; ".join(
            "[void][scriptblock]::Create((Get-Content -Raw "
            f"'/workspace/{path.relative_to(ROOT).as_posix()}'))"
            for path in ps_scripts
        )
        check = run_command(
            "powershell_parse",
            "automation",
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "--volume",
                f"{ROOT}:/workspace:ro",
                "--entrypoint",
                "pwsh",
                POWERSHELL_IMAGE,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                container_expression,
            ],
        )
        check.measurements = {
            "scripts_present": len(ps_scripts),
            "runtime": "PowerShell 7.5 container (linux/amd64 emulation)",
        }
        checks.append(check)
    else:
        status = "failed" if require_powershell else "skipped"
        checks.append(
            Check(
                name="powershell_parse",
                category="automation",
                status=status,
                detail="pwsh runtime is not installed",
                measurements={"scripts_present": len(ps_scripts)},
            )
        )
    return checks


def run_terraform_checks(require_terraform: bool) -> list[Check]:
    if not command_available("terraform"):
        status = "failed" if require_terraform else "skipped"
        return [
            Check(
                name="terraform_validation",
                category="infrastructure",
                status=status,
                detail="terraform CLI is not installed",
                measurements={"configurations_present": 2},
            )
        ]

    checks: list[Check] = []
    for directory in (ROOT / "infra" / "kubernetes", ROOT / "infra" / "azure"):
        relative = str(directory.relative_to(ROOT))
        checks.append(
            run_command(
                f"terraform_fmt_{directory.name}",
                "infrastructure",
                ["terraform", f"-chdir={relative}", "fmt", "-check", "-recursive"],
            )
        )
        init = run_command(
            f"terraform_init_{directory.name}",
            "infrastructure",
            [
                "terraform",
                f"-chdir={relative}",
                "init",
                "-backend=false",
                "-input=false",
                "-no-color",
            ],
        )
        checks.append(init)
        if init.status == "passed":
            checks.append(
                run_command(
                    f"terraform_validate_{directory.name}",
                    "infrastructure",
                    ["terraform", f"-chdir={relative}", "validate", "-no-color"],
                )
            )
        else:
            checks.append(
                Check(
                    name=f"terraform_validate_{directory.name}",
                    category="infrastructure",
                    status="failed",
                    detail="not run because terraform init failed",
                )
            )
    return checks


def request_json(url: str) -> tuple[int, dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=3) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def request_text(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=3) as response:
        return (
            response.status,
            response.headers.get("Content-Type", ""),
            response.read().decode("utf-8"),
        )


def wait_until_live(base_url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status_code, payload = request_json(f"{base_url}/health/live")
            if status_code == 200 and payload == {"status": "live"}:
                return
        except (OSError, urllib.error.URLError, ValueError) as exc:
            last_error = exc
        time.sleep(0.5)
    raise TimeoutError(f"container did not become live: {last_error}")


def run_docker_checks(require_docker: bool, release_id: str, revision: str) -> list[Check]:
    docker_status = run_command(
        "docker_daemon",
        "container",
        ["docker", "info", "--format", "{{.ServerVersion}}"],
    )
    if not command_available("docker") or docker_status.status == "failed":
        status = "failed" if require_docker else "skipped"
        return [
            Check(
                name="docker_runtime",
                category="container",
                status=status,
                command=docker_status.command,
                duration_seconds=docker_status.duration_seconds,
                detail="Docker CLI is missing or daemon is unreachable",
                output_tail=docker_status.output_tail,
            )
        ]

    safe_release = re.sub(r"[^a-z0-9_.-]", "-", release_id.lower())[:50]
    image = f"cloud-release-reliability-lab:evidence-{safe_release}"
    checks: list[Check] = [docker_status]
    build = run_command(
        "docker_build",
        "container",
        [
            "docker",
            "build",
            "--pull",
            "--label",
            f"lab.release.id={release_id}",
            "--tag",
            image,
            ".",
        ],
    )
    checks.append(build)
    if build.status == "failed":
        return checks

    identity = run_command(
        "container_non_root",
        "container",
        ["docker", "run", "--rm", "--entrypoint", "id", image, "-u"],
    )
    identity.measurements["runtime_uid"] = identity.output_tail.strip()
    if identity.status == "passed" and identity.output_tail.strip() == "0":
        identity.status = "failed"
        identity.detail = "container unexpectedly ran as root"
    checks.append(identity)

    inspect = run_command(
        "docker_image_inspect",
        "container",
        ["docker", "image", "inspect", image, "--format", "{{.Size}}|{{.Config.User}}|{{.Id}}"],
    )
    if inspect.status == "passed":
        fields = inspect.output_tail.split("|", maxsplit=2)
        if len(fields) == 3 and fields[0].isdigit():
            inspect.measurements.update(
                {
                    "image_size_bytes": int(fields[0]),
                    "configured_user": fields[1],
                    "image_id": fields[2],
                }
            )
    checks.append(inspect)

    container_name = f"release-evidence-{os.getpid()}"
    run = run_command(
        "container_start",
        "container",
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            container_name,
            "--publish",
            "127.0.0.1::8080",
            "--env",
            f"RELEASE_VERSION={release_id}",
            "--env",
            f"RELEASE_COMMIT_SHA={revision}",
            "--env",
            "RELEASE_ENVIRONMENT=evidence-container",
            image,
        ],
    )
    checks.append(run)
    if run.status == "failed":
        return checks

    try:
        port = run_command(
            "container_port",
            "container",
            ["docker", "port", container_name, "8080/tcp"],
        )
        checks.append(port)
        if port.status == "failed":
            return checks
        host_port = port.output_tail.rsplit(":", maxsplit=1)[-1]
        base_url = f"http://127.0.0.1:{host_port}"
        smoke_started = time.monotonic()
        try:
            wait_until_live(base_url)
            live_status, live = request_json(f"{base_url}/health/live")
            ready_status, ready = request_json(f"{base_url}/health/ready")
            version_status, version = request_json(f"{base_url}/version")
            metrics_status, content_type, metrics = request_text(f"{base_url}/metrics")
            assertions = [
                live_status == 200 and live == {"status": "live"},
                ready_status == 200 and ready == {"status": "ready"},
                version_status == 200,
                version.get("version") == release_id,
                version.get("commit_sha") == revision,
                metrics_status == 200,
                content_type.startswith("text/plain; version=0.0.4"),
                "release_service_ready 1" in metrics,
            ]
            if not all(assertions):
                raise AssertionError("one or more endpoint assertions failed")
            smoke = Check(
                name="container_smoke",
                category="container",
                status="passed",
                duration_seconds=round(time.monotonic() - smoke_started, 3),
                detail="live, ready, version, and metrics assertions passed",
                measurements={
                    "endpoints_checked": len(OPERATIONAL_ENDPOINTS),
                    "endpoints": list(OPERATIONAL_ENDPOINTS),
                },
            )
        except Exception as exc:
            logs = run_command("container_logs", "diagnostic", ["docker", "logs", container_name])
            smoke = Check(
                name="container_smoke",
                category="container",
                status="failed",
                duration_seconds=round(time.monotonic() - smoke_started, 3),
                detail=str(exc),
                output_tail=logs.output_tail,
            )
        checks.append(smoke)
    finally:
        run_command("container_cleanup", "container", ["docker", "rm", "--force", container_name])
    return checks


def cluster_observation() -> Check:
    if not command_available("kubectl"):
        return skipped("kubernetes_runtime", "orchestration", "kubectl is not installed")
    context = run_command(
        "kubernetes_context",
        "orchestration",
        ["kubectl", "config", "current-context"],
    )
    if context.status == "failed":
        return Check(
            name="kubernetes_runtime",
            category="orchestration",
            status="skipped",
            detail="no configured Kubernetes context; no rollout was executed",
            output_tail=context.output_tail,
        )
    cluster = run_command("kubernetes_cluster_info", "orchestration", ["kubectl", "cluster-info"])
    if cluster.status == "failed":
        cluster.name = "kubernetes_runtime"
        cluster.status = "skipped"
        cluster.detail = "configured context is unreachable; no rollout was executed"
    else:
        cluster.name = "kubernetes_runtime"
        cluster.measurements["context"] = context.output_tail.strip()
        cluster.detail = (
            "reachable cluster detected; deployment remains an explicit operator action"
        )
    return cluster


def verify_kubernetes_evidence(path: Path) -> Check:
    """Validate explicit command-generated drill evidence before incorporating its claim."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Check(
            name="kubernetes_drill_evidence",
            category="orchestration",
            status="failed",
            detail=f"could not read drill evidence: {exc}",
        )

    required_truths = (
        report.get("status") == "passed",
        report.get("failure_observed") is True,
        report.get("rollback_recovered") is True,
        report.get("post_recovery_smoke_executed") is True,
    )
    desired = report.get("desired_replicas")
    during = report.get("ready_replicas_during_failure")
    after = report.get("ready_replicas_after_recovery")
    replica_values_are_valid = all(isinstance(value, int) for value in (desired, during, after))
    capacity_retained = bool(
        replica_values_are_valid and during >= desired >= 1 and after >= desired
    )
    if not all(required_truths) or not capacity_retained:
        return Check(
            name="kubernetes_drill_evidence",
            category="orchestration",
            status="failed",
            detail="drill evidence does not prove failure, retained capacity, rollback, and smoke",
            measurements={"source": str(path)},
        )
    return Check(
        name="kubernetes_drill_evidence",
        category="orchestration",
        status="passed",
        detail="command-generated failure and rollback evidence verified",
        measurements={
            "source": str(path),
            "desired_replicas": desired,
            "ready_during_failure": during,
            "ready_after_recovery": after,
            "duration_seconds": report.get("duration_seconds"),
            "before_revision": report.get("before_revision"),
            "after_revision": report.get("after_revision"),
        },
    )


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    boundaries = report["claim_boundaries"]
    docker_executed = str(boundaries["docker_executed"]).lower()
    kubernetes_executed = str(boundaries["kubernetes_rollout_executed"]).lower()
    azure_executed = str(boundaries["azure_deployment_executed"]).lower()
    ci_executed = str(boundaries["ci_run_executed"]).lower()
    lines = [
        "# Local validation evidence",
        "",
        f"- Generated (UTC): `{report['generated_at']}`",
        f"- Release: `{report['release_id']}`",
        f"- Revision: `{report['revision']}`",
        f"- Overall result: **{report['overall_status'].upper()}**",
        "- Passed / failed / skipped: "
        f"**{summary['passed']} / {summary['failed']} / {summary['skipped']}**",
        "",
        "## Executed checks",
        "",
        "| Check | Scope | Result | Measurement or boundary |",
        "|---|---|---:|---|",
    ]
    for check in report["checks"]:
        measurement = check["detail"]
        if check["measurements"]:
            measurement = f"{measurement}; `{json.dumps(check['measurements'], sort_keys=True)}`"
        lines.append(
            f"| `{check['name']}` | {check['category']} | **{check['status']}** | {measurement} |"
        )

    lines.extend(
        [
            "",
            "## Claim boundaries",
            "",
            f"- Docker runtime validated in this run: **{docker_executed}**.",
            "- Kubernetes rollout/failure drill validated in this run: "
            f"**{kubernetes_executed}**.",
            f"- Azure deployment validated in this run: **{azure_executed}**.",
            f"- GitHub Actions run validated in this run: **{ci_executed}**.",
            "",
            "Skipped checks are boundaries, not successes. See the JSON file for "
            "command output tails and exact measurements.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--release-id", default=None)
    parser.add_argument("--require-docker", action="store_true")
    parser.add_argument("--require-terraform", action="store_true")
    parser.add_argument("--require-powershell", action="store_true")
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--skip-terraform", action="store_true")
    parser.add_argument(
        "--kubernetes-evidence",
        type=Path,
        default=None,
        help="explicit command-generated drill JSON to include in claim boundaries",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(tz=UTC)
    revision = git_revision()
    release_id = args.release_id or f"local-{generated_at.strftime('%Y%m%dT%H%M%SZ')}"

    checks = [repository_contract_check()]
    checks.extend(run_python_checks(output_dir))
    checks.extend(run_script_checks(args.require_powershell))
    if args.skip_terraform:
        checks.append(
            skipped(
                "terraform_validation",
                "infrastructure",
                "disabled by --skip-terraform",
            )
        )
    else:
        checks.extend(run_terraform_checks(args.require_terraform))
    if args.skip_docker:
        checks.append(skipped("docker_runtime", "container", "disabled by --skip-docker"))
    else:
        checks.extend(run_docker_checks(args.require_docker, release_id, revision))
    checks.append(cluster_observation())
    if args.kubernetes_evidence is not None:
        checks.append(verify_kubernetes_evidence(args.kubernetes_evidence.resolve()))

    counts = {
        status: sum(check.status == status for check in checks)
        for status in ("passed", "failed", "skipped")
    }
    report = {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(),
        "release_id": release_id,
        "revision": revision,
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "overall_status": "passed" if counts["failed"] == 0 else "failed",
        "summary": counts,
        "checks": [asdict(check) for check in checks],
        "claim_boundaries": {
            "docker_executed": any(
                check.name == "container_smoke" and check.status == "passed" for check in checks
            ),
            "kubernetes_rollout_executed": any(
                check.name == "kubernetes_drill_evidence" and check.status == "passed"
                for check in checks
            ),
            "azure_deployment_executed": False,
            # A report created inside a job cannot prove that the job later completed.
            "ci_run_executed": False,
        },
        "execution_environment": {
            "github_actions": os.getenv("GITHUB_ACTIONS") == "true",
        },
    }

    json_path = output_dir / "local-validation.json"
    markdown_path = output_dir / "local-validation.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"evidence_json={json_path}")
    print(f"evidence_markdown={markdown_path}")
    print(f"result={report['overall_status']}")
    print(f"passed={counts['passed']} failed={counts['failed']} skipped={counts['skipped']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
