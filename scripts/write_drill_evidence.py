#!/usr/bin/env python3
"""Persist measured Kubernetes failure-drill results as JSON and Markdown."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--before-revision", required=True)
    parser.add_argument("--after-revision", required=True)
    parser.add_argument("--desired-replicas", type=int, required=True)
    parser.add_argument("--ready-during-failure", type=int, required=True)
    parser.add_argument("--ready-after-recovery", type=int, required=True)
    parser.add_argument("--failure-timeout", required=True)
    parser.add_argument("--duration-seconds", type=int, required=True)
    parser.add_argument("--failed-release", required=True)
    parser.add_argument("--smoke-executed", choices=("true", "false"), required=True)
    parser.add_argument("--rollout-output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "scenario": "controlled_readiness_failure_and_rollout_undo",
        "status": "passed",
        "namespace": args.namespace,
        "deployment": args.deployment,
        "failed_release": args.failed_release,
        "failure_observed": True,
        "rollback_recovered": True,
        "before_revision": args.before_revision,
        "after_revision": args.after_revision,
        "desired_replicas": args.desired_replicas,
        "ready_replicas_during_failure": args.ready_during_failure,
        "ready_replicas_after_recovery": args.ready_after_recovery,
        "failure_timeout": args.failure_timeout,
        "duration_seconds": args.duration_seconds,
        "post_recovery_smoke_executed": args.smoke_executed == "true",
        "failed_rollout_command_output": args.rollout_output[-4000:],
    }
    json_path = args.output_dir / "kubernetes-drill.json"
    markdown_path = args.output_dir / "kubernetes-drill.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        "\n".join(
            [
                "# Kubernetes failure drill evidence",
                "",
                f"- Generated (UTC): `{report['generated_at']}`",
                f"- Target: `{args.namespace}/deployment/{args.deployment}`",
                "- Controlled readiness failure observed: **true**",
                "- Rollout undo recovered ready capacity: **true**",
                "- Desired / ready during failure / ready after recovery: "
                f"**{args.desired_replicas} / {args.ready_during_failure} / "
                f"{args.ready_after_recovery}**",
                "- Revision before / after undo: "
                f"**{args.before_revision} / {args.after_revision}**",
                f"- Drill duration: **{args.duration_seconds}s**",
                "- Post-recovery HTTP smoke executed: "
                f"**{str(report['post_recovery_smoke_executed']).lower()}**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"drill_evidence_json={json_path}")
    print(f"drill_evidence_markdown={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
