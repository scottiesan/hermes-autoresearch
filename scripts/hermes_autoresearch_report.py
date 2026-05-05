"""Report generation helpers for Hermes autoresearch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_markdown(run: dict[str, Any]) -> str:
    lines = [
        f"# Hermes Autoresearch: {run.get('name', 'run')}",
        "",
        f"- Started: {run.get('started_at')}",
        f"- Finished: {run.get('finished_at')}",
        f"- Repo: `{run.get('repo_path')}`",
        f"- Branch: `{run.get('branch')}`",
        f"- Baseline score: `{run.get('baseline_score')}`",
        f"- Final score: `{run.get('final_score')}`",
        f"- Accepted: `{run.get('accepted_count', 0)}`",
        f"- Rejected: `{run.get('rejected_count', 0)}`",
        "",
        "## Iterations",
        "",
    ]
    for item in run.get("iterations", []):
        status = "accepted" if item.get("accepted") else "rejected"
        lines.extend(
            [
                f"### Iteration {item.get('iteration'):03d}: {status}",
                "",
                f"- Before: `{item.get('score_before')}`",
                f"- After: `{item.get('score_after')}`",
                f"- Improved: `{item.get('improved')}`",
                f"- Guard pass: `{item.get('guard_pass')}`",
                f"- Safety pass: `{item.get('safety_pass')}`",
                f"- Reason: {item.get('reason')}",
                f"- Commit: `{item.get('commit') or ''}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_reports(results_dir: Path, run: dict[str, Any]) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "run.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    (results_dir / "run.md").write_text(render_markdown(run), encoding="utf-8")


def load_run_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
