import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "hermes_autoresearch.py"


def run(cmd, cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, **kwargs)


def init_repo(repo: Path) -> None:
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)


def write_config(path: Path, repo: Path, worker: str, max_iterations: int = 1) -> None:
    config = {
        "name": "cli-e2e",
        "repo_path": str(repo),
        "branch_prefix": "autoresearch-e2e",
        "goal": "Reduce the numeric metric",
        "scope": ["src/"],
        "metric": {
            "command": f"{sys.executable} metric.py",
            "parser": "numeric_stdout",
            "direction": "lower",
        },
        "verify": {"command": f"{sys.executable} metric.py"},
        "guard": {"command": f"{sys.executable} -m compileall src"},
        "safety": {
            "require_clean_git": True,
            "forbid_paths": [".env", "*.pem"],
            "forbid_patterns": ["LIVE_TRADING=true", "place_order("],
        },
        "agent": {
            "type": "codex_cli",
            "command": f"{sys.executable} {worker}",
            "timeout_seconds": 30,
        },
        "loop": {
            "max_iterations": max_iterations,
            "one_atomic_change": True,
            "revert_on_fail": True,
            "commit_on_success": True,
        },
        "results": {"dir": "autoresearch-results", "save_diff": True, "save_logs": True},
    }
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def test_cli_run_commits_accepted_change_and_writes_report(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "metric.py").write_text(
        "from pathlib import Path\nprint(Path('src/app.py').read_text().count('VALUE = 2'))\n",
        encoding="utf-8",
    )
    (repo / "worker.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "assert 'Reduce the numeric metric' in prompt\n"
        "Path('src/app.py').write_text('VALUE = 1\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "initial"], repo)

    config = tmp_path / "autoresearch.yaml"
    write_config(config, repo, "worker.py")

    result = run([sys.executable, str(CLI), "run", "--config", str(config)], ROOT)
    assert "final_score: 0.0" in result.stdout

    run_json = json.loads((repo / "autoresearch-results" / "run.json").read_text(encoding="utf-8"))
    assert run_json["accepted_count"] == 1
    assert run_json["rejected_count"] == 0
    assert run_json["iterations"][0]["commit"]
    assert (repo / "autoresearch-results" / "iteration-001-prompt.md").exists()
    assert "VALUE = 1" in (repo / "src" / "app.py").read_text(encoding="utf-8")

    git_log = run(["git", "log", "--oneline", "-1"], repo).stdout
    assert "autoresearch: accept iteration 001" in git_log

    report = run([sys.executable, str(CLI), "report", "--config", str(config)], ROOT).stdout
    assert "Accepted: `1`" in report


def test_cli_run_reverts_rejected_change(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "metric.py").write_text(
        "from pathlib import Path\nprint(Path('src/app.py').read_text().count('VALUE = 2'))\n",
        encoding="utf-8",
    )
    (repo / "worker.py").write_text(
        "from pathlib import Path\n"
        "Path('src/app.py').write_text('LIVE_TRADING=true\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "initial"], repo)

    config = tmp_path / "autoresearch.yaml"
    write_config(config, repo, "worker.py")

    run([sys.executable, str(CLI), "run", "--config", str(config)], ROOT)

    run_json = json.loads((repo / "autoresearch-results" / "run.json").read_text(encoding="utf-8"))
    assert run_json["accepted_count"] == 0
    assert run_json["rejected_count"] == 1
    assert "forbidden pattern" in run_json["iterations"][0]["reason"]
    assert "LIVE_TRADING=true" not in (repo / "src" / "app.py").read_text(encoding="utf-8")
