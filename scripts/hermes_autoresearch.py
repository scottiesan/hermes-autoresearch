#!/usr/bin/env python3
"""Hermes-native autoresearch supervisor CLI."""

from __future__ import annotations

import argparse
import fnmatch
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc

try:
    from .hermes_autoresearch_report import write_reports
    from .hermes_autoresearch_score import CommandResult, ScoreError, improved, parse_score
except ImportError:  # pragma: no cover - direct script execution
    from hermes_autoresearch_report import write_reports
    from hermes_autoresearch_score import CommandResult, ScoreError, improved, parse_score


REQUIRED_TOP_LEVEL = ["name", "repo_path", "branch_prefix", "goal", "scope", "metric", "verify", "guard", "safety", "agent", "loop", "results"]
TRADING_FORBIDDEN_PATTERNS = [
    "EXECUTION_ENABLED=true",
    "LIVE_TRADING=true",
    "place_order(",
    "submit_order(",
    "send_order(",
]


@dataclass
class RunCommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must be a YAML mapping")
    validate_config(data)
    data["_config_path"] = str(path.resolve())
    data["repo_path"] = str(Path(data["repo_path"]).expanduser().resolve())
    return data


def validate_config(config: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_TOP_LEVEL if key not in config]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    if config["metric"].get("parser") not in {"failing_tests", "grep_count", "numeric_stdout", "exit_code"}:
        raise ValueError("metric.parser must be failing_tests, grep_count, numeric_stdout, or exit_code")
    if config["metric"].get("direction") not in {"lower", "higher"}:
        raise ValueError("metric.direction must be lower or higher")
    if not isinstance(config.get("scope"), list) or not config["scope"]:
        raise ValueError("scope must be a non-empty list")
    if config["agent"].get("type") != "codex_cli":
        raise ValueError("only agent.type=codex_cli is supported")
    if int(config["loop"].get("max_iterations", 0)) < 1:
        raise ValueError("loop.max_iterations must be at least 1")


def run_command(command: str, cwd: Path, timeout: int | None = None) -> RunCommandResult:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return RunCommandResult(proc.returncode, proc.stdout, proc.stderr)


def git(args: list[str], repo: Path, check: bool = True) -> RunCommandResult:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    wrapped = RunCommandResult(result.returncode, result.stdout, result.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{wrapped.combined}")
    return wrapped


def ensure_repo_ready(config: dict[str, Any], dry_run: bool = False) -> Path:
    repo = Path(config["repo_path"])
    if not repo.exists():
        raise FileNotFoundError(f"repo_path does not exist: {repo}")
    if dry_run:
        return repo
    git(["rev-parse", "--show-toplevel"], repo)
    if config["safety"].get("require_clean_git", True):
        status = git(["status", "--porcelain"], repo).stdout.strip()
        if status:
            raise RuntimeError("git working tree must be clean before autoresearch starts")
    return repo


def create_branch(config: dict[str, Any], repo: Path) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in config["name"])
    branch = f"{config['branch_prefix']}/{safe_name}-{stamp}"
    git(["checkout", "-b", branch], repo)
    return branch


def rel_to_repo(repo: Path, path: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def is_under_results(path: str, results_rel: str) -> bool:
    return path == results_rel or path.startswith(results_rel.rstrip("/") + "/")


def changed_files(repo: Path, results_dir: Path) -> list[str]:
    results_rel = rel_to_repo(repo, results_dir)
    out = git(["status", "--porcelain"], repo).stdout
    files: list[str] = []
    for line in out.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if is_under_results(path, results_rel):
            continue
        files.append(path)
    return sorted(set(files))


def is_tracked(repo: Path, path: str) -> bool:
    return git(["ls-files", "--error-unmatch", "--", path], repo, check=False).returncode == 0


def git_diff(repo: Path, files: list[str]) -> str:
    if not files:
        return ""
    tracked = [path for path in files if is_tracked(repo, path)]
    chunks: list[str] = []
    if tracked:
        chunks.append(git(["diff", "--", *tracked], repo).stdout)
    for path in files:
        if is_tracked(repo, path):
            continue
        full_path = repo / path
        if full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = "<binary or non-utf8 file>\n"
            chunks.append(f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n" + "".join(f"+{line}" for line in content.splitlines(True)))
    return "\n".join(chunk for chunk in chunks if chunk)


def is_path_forbidden(path: str, patterns: list[str]) -> bool:
    norm = path.replace(os.sep, "/")
    for pattern in patterns:
        pat = pattern.replace(os.sep, "/")
        if pat.endswith("/"):
            if norm == pat[:-1] or norm.startswith(pat):
                return True
        elif fnmatch.fnmatch(norm, pat) or norm == pat:
            return True
    return False


def is_path_in_scope(path: str, scope: list[str]) -> bool:
    norm = path.replace(os.sep, "/")
    for item in scope:
        scoped = item.replace(os.sep, "/")
        if scoped.endswith("/"):
            if norm.startswith(scoped):
                return True
        elif norm == scoped or norm.startswith(scoped.rstrip("/") + "/"):
            return True
    return False


def safety_check(config: dict[str, Any], files: list[str], diff_text: str) -> tuple[bool, str]:
    if not files:
        return False, "worker made no changes"
    forbidden_paths = list(config["safety"].get("forbid_paths", []))
    for path in files:
        if is_path_forbidden(path, forbidden_paths):
            return False, f"forbidden path changed: {path}"
    allow_outside = bool(config["safety"].get("allow_outside_scope", False))
    if not allow_outside:
        for path in files:
            if not is_path_in_scope(path, config["scope"]):
                return False, f"changed file outside scope: {path}"
    forbidden_patterns = list(config["safety"].get("forbid_patterns", []))
    for hard_rule in TRADING_FORBIDDEN_PATTERNS:
        if hard_rule not in forbidden_patterns:
            forbidden_patterns.append(hard_rule)
    for pattern in forbidden_patterns:
        if pattern and pattern in diff_text:
            return False, f"forbidden pattern found in diff: {pattern}"
    return True, "safety checks passed"


def score_metric(config: dict[str, Any], repo: Path, log_path: Path | None = None) -> tuple[float | None, RunCommandResult, str | None]:
    metric = config["metric"]
    result = run_command(metric["command"], repo, timeout=int(config["agent"].get("timeout_seconds", 900)))
    if log_path:
        log_path.write_text(result.combined, encoding="utf-8")
    try:
        score = parse_score(metric["parser"], CommandResult(result.returncode, result.stdout, result.stderr))
    except ScoreError as exc:
        return None, result, str(exc)
    return score, result, None


def score_command_result(config: dict[str, Any], result: RunCommandResult) -> tuple[float | None, str | None]:
    try:
        score = parse_score(
            config["metric"]["parser"],
            CommandResult(result.returncode, result.stdout, result.stderr),
        )
    except ScoreError as exc:
        return None, str(exc)
    return score, None


def run_verify(config: dict[str, Any], repo: Path, log_path: Path) -> RunCommandResult:
    result = run_command(config["verify"]["command"], repo, timeout=int(config["agent"].get("timeout_seconds", 900)))
    log_path.write_text(result.combined, encoding="utf-8")
    return result


def run_guard(config: dict[str, Any], repo: Path, log_path: Path) -> RunCommandResult:
    result = run_command(config["guard"]["command"], repo, timeout=int(config["agent"].get("timeout_seconds", 900)))
    log_path.write_text(result.combined, encoding="utf-8")
    return result


def render_worker_prompt(config: dict[str, Any], iteration: int, score: float) -> str:
    forbidden_paths = "\n".join(f"- {item}" for item in config["safety"].get("forbid_paths", []))
    forbidden_patterns = "\n".join(f"- {item}" for item in config["safety"].get("forbid_patterns", []))
    scope = "\n".join(f"- {item}" for item in config["scope"])
    return f"""# Hermes Autoresearch Iteration {iteration:03d}

Hermes is supervising this run. You are the Codex CLI worker.

Goal:
{config["goal"]}

Current score: {score}
Metric direction: {config["metric"]["direction"]}

Allowed scope:
{scope}

Forbidden paths:
{forbidden_paths}

Forbidden patterns:
{forbidden_patterns}

Verify command:
`{config["verify"]["command"]}`

Guard command:
`{config["guard"]["command"]}`

Make exactly one atomic change that can improve the score. Never enable live trading, live execution, broker credentials, wallet access, or order placement. Do not modify .env, secrets, private keys, wallets, or production execution configs.

Stop after editing. Hermes will run verification, scoring, safety checks, commits, and reverts.
"""


def run_worker(config: dict[str, Any], repo: Path, prompt_path: Path, log_path: Path) -> RunCommandResult:
    command = f"{config['agent']['command']} {shlex.quote(prompt_path.read_text(encoding='utf-8'))}"
    result = run_command(command, repo, timeout=int(config["agent"].get("timeout_seconds", 900)))
    log_path.write_text(result.combined, encoding="utf-8")
    return result


def decide_accept(
    score_before: float,
    score_after: float | None,
    direction: str,
    worker_pass: bool,
    guard_pass: bool,
    safety_pass: bool,
    safety_reason: str,
    verify_score_error: str | None,
) -> tuple[bool, bool, str]:
    if score_after is None:
        return False, False, f"verify command cannot be scored: {verify_score_error}"
    did_improve = improved(score_before, score_after, direction)
    if not worker_pass:
        return False, did_improve, "worker command failed"
    if not did_improve:
        return False, did_improve, "score did not improve"
    if not guard_pass:
        return False, did_improve, "guard command failed"
    if not safety_pass:
        return False, did_improve, safety_reason
    return True, did_improve, "score improved and checks passed"


def revert_changes(repo: Path, files: list[str]) -> None:
    tracked = [path for path in files if is_tracked(repo, path)]
    untracked = [path for path in files if not is_tracked(repo, path)]
    if tracked:
        git(["checkout", "--", *tracked], repo)
    for path in untracked:
        target = repo / path
        if target.is_file() or target.is_symlink():
            target.unlink()
        elif target.is_dir():
            import shutil

            shutil.rmtree(target)


def commit_changes(config: dict[str, Any], repo: Path, files: list[str], iteration: int, score_before: float, score_after: float) -> str:
    git(["add", "--", *files], repo)
    message = f"autoresearch: accept iteration {iteration:03d}\n\nScore: {score_before} -> {score_after}\nGoal: {config['goal']}"
    git(["commit", "-m", message], repo)
    return git(["rev-parse", "--short", "HEAD"], repo).stdout.strip()


def run_loop(config: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    repo = ensure_repo_ready(config, dry_run=dry_run)
    results_dir = repo / config["results"].get("dir", "autoresearch-results")
    if dry_run:
        return {
            "name": config["name"],
            "started_at": utc_now(),
            "finished_at": utc_now(),
            "repo_path": str(repo),
            "branch": None,
            "baseline_score": None,
            "final_score": None,
            "accepted_count": 0,
            "rejected_count": 0,
            "iterations": [],
            "dry_run": True,
        }

    results_dir.mkdir(parents=True, exist_ok=True)
    branch = create_branch(config, repo)
    baseline_score, baseline_result, baseline_error = score_metric(config, repo, results_dir / "baseline.log")
    if baseline_score is None:
        raise RuntimeError(f"baseline metric cannot be scored: {baseline_error}\n{baseline_result.combined}")

    run: dict[str, Any] = {
        "name": config["name"],
        "started_at": utc_now(),
        "finished_at": None,
        "repo_path": str(repo),
        "branch": branch,
        "baseline_score": baseline_score,
        "final_score": baseline_score,
        "accepted_count": 0,
        "rejected_count": 0,
        "iterations": [],
    }
    current_score = baseline_score
    max_iterations = int(config["loop"]["max_iterations"])

    for iteration in range(1, max_iterations + 1):
        score_before = current_score
        prompt_path = results_dir / f"iteration-{iteration:03d}-prompt.md"
        agent_log = results_dir / f"iteration-{iteration:03d}-agent.log"
        verify_log = results_dir / f"iteration-{iteration:03d}-verify.log"
        guard_log = results_dir / f"iteration-{iteration:03d}-guard.log"
        diff_path = results_dir / f"iteration-{iteration:03d}.diff"

        prompt_path.write_text(render_worker_prompt(config, iteration, current_score), encoding="utf-8")
        worker_result = run_worker(config, repo, prompt_path, agent_log)
        files = changed_files(repo, results_dir)
        diff_text = git_diff(repo, files)
        if config["results"].get("save_diff", True):
            diff_path.write_text(diff_text, encoding="utf-8")

        verify_result = run_verify(config, repo, verify_log)
        guard_result = run_guard(config, repo, guard_log)
        score_after, score_error = score_command_result(config, verify_result)
        safety_pass, safety_reason = safety_check(config, files, diff_text)
        accepted, did_improve, reason = decide_accept(
            current_score,
            score_after,
            config["metric"]["direction"],
            worker_result.returncode == 0,
            guard_result.returncode == 0,
            safety_pass,
            safety_reason,
            score_error,
        )

        commit_hash = None
        if accepted and config["loop"].get("commit_on_success", True):
            commit_hash = commit_changes(config, repo, files, iteration, score_before, float(score_after))
            current_score = float(score_after)
            run["accepted_count"] += 1
        else:
            if config["loop"].get("revert_on_fail", True):
                revert_changes(repo, files)
            run["rejected_count"] += 1

        run["iterations"].append(
            {
                "iteration": iteration,
                "score_before": score_before,
                "score_after": score_after,
                "improved": did_improve,
                "guard_pass": guard_result.returncode == 0,
                "safety_pass": safety_pass,
                "accepted": accepted,
                "reason": reason,
                "commit": commit_hash,
                "worker_returncode": worker_result.returncode,
                "verify_returncode": verify_result.returncode,
            }
        )
        run["final_score"] = current_score
        write_reports(results_dir, run)

    run["finished_at"] = utc_now()
    write_reports(results_dir, run)
    return run


def plan(config: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    repo = ensure_repo_ready(config, dry_run=True)
    return {
        "name": config["name"],
        "repo_path": str(repo),
        "goal": config["goal"],
        "metric": config["metric"],
        "iterations": int(config["loop"]["max_iterations"]),
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hermes autoresearch supervisor")
    parser.add_argument("subcommand", nargs="?", choices=["plan", "run", "report"], default="run")
    parser.add_argument("--config", required=True, help="Path to autoresearch YAML config")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print planned run without touching git")
    args = parser.parse_args(argv)

    try:
        config = load_config(Path(args.config))
        if args.subcommand == "plan" or args.dry_run:
            print_yaml(plan(config, dry_run=args.dry_run))
            return 0
        if args.subcommand == "report":
            repo = ensure_repo_ready(config, dry_run=True)
            results_dir = repo / config["results"].get("dir", "autoresearch-results")
            run_path = results_dir / "run.json"
            if not run_path.exists():
                raise FileNotFoundError(f"no run.json found at {run_path}")
            try:
                from .hermes_autoresearch_report import load_run_json, render_markdown
            except ImportError:  # pragma: no cover - direct script execution
                from hermes_autoresearch_report import load_run_json, render_markdown

            print(render_markdown(load_run_json(run_path)))
            return 0
        run = run_loop(config, dry_run=False)
        print_yaml({"run": run["name"], "branch": run["branch"], "final_score": run["final_score"]})
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def print_yaml(data: dict[str, Any]) -> None:
    print(yaml.safe_dump(data, sort_keys=False).strip())


if __name__ == "__main__":
    raise SystemExit(main())
