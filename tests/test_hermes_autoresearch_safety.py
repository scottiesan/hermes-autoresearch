import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hermes_autoresearch import decide_accept, is_path_forbidden, is_path_in_scope, run_loop, safety_check, validate_config


def base_config(tmp_path: Path) -> dict:
    return {
        "name": "test-run",
        "repo_path": str(tmp_path),
        "branch_prefix": "autoresearch-test",
        "goal": "improve tests",
        "scope": ["src/", "tests/"],
        "metric": {"command": "python metric.py", "parser": "numeric_stdout", "direction": "lower"},
        "verify": {"command": "python metric.py"},
        "guard": {"command": "python -m compileall ."},
        "safety": {
            "require_clean_git": True,
            "forbid_paths": [".env", "secrets/", "*.pem"],
            "forbid_patterns": ["LIVE_TRADING=true", "place_order("],
        },
        "agent": {"type": "codex_cli", "command": "python worker.py", "timeout_seconds": 30},
        "loop": {
            "max_iterations": 1,
            "one_atomic_change": True,
            "revert_on_fail": True,
            "commit_on_success": True,
        },
        "results": {"dir": "autoresearch-results", "save_diff": True, "save_logs": True},
    }


def init_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)


def test_forbidden_path_detection():
    assert is_path_forbidden(".env", [".env"]) is True
    assert is_path_forbidden("secrets/token.txt", ["secrets/"]) is True
    assert is_path_forbidden("certs/prod.pem", ["*.pem"]) is True
    assert is_path_forbidden("src/app.py", [".env"]) is False


def test_forbidden_pattern_detection(tmp_path):
    config = base_config(tmp_path)
    passed, reason = safety_check(config, ["src/app.py"], "+LIVE_TRADING=true\n")
    assert passed is False
    assert "forbidden pattern" in reason


def test_no_change_rejection(tmp_path):
    config = base_config(tmp_path)
    passed, reason = safety_check(config, [], "")
    assert passed is False
    assert reason == "worker made no changes"


def test_outside_scope_rejection(tmp_path):
    config = base_config(tmp_path)
    passed, reason = safety_check(config, ["docs/readme.md"], "+text\n")
    assert passed is False
    assert "outside scope" in reason
    assert is_path_in_scope("src/app.py", ["src/"]) is True
    assert is_path_in_scope("docs/readme.md", ["src/"]) is False


def test_accepted_rejected_decision_logic():
    accepted, did_improve, reason = decide_accept(3, 2, "lower", True, True, True, "ok", None)
    assert (accepted, did_improve, reason) == (True, True, "score improved and checks passed")

    accepted, did_improve, reason = decide_accept(3, 4, "lower", True, True, True, "ok", None)
    assert accepted is False
    assert did_improve is False
    assert reason == "score did not improve"

    accepted, did_improve, reason = decide_accept(3, 2, "lower", True, False, True, "ok", None)
    assert accepted is False
    assert did_improve is True
    assert reason == "guard command failed"


def test_worker_failure_rejects_even_when_score_improves():
    accepted, did_improve, reason = decide_accept(3, 2, "lower", False, True, True, "ok", None)
    assert accepted is False
    assert did_improve is True
    assert reason == "worker command failed"


def test_validate_config_rejects_results_dir_outside_repo(tmp_path):
    config = base_config(tmp_path)
    config["results"]["dir"] = "../outside"
    with pytest.raises(ValueError, match="results.dir"):
        validate_config(config)


def test_validate_config_rejects_missing_agent_command(tmp_path):
    config = base_config(tmp_path)
    config["agent"]["command"] = ""
    with pytest.raises(ValueError, match="agent.command"):
        validate_config(config)


def test_loop_can_run_one_mocked_accepted_iteration(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "metric.py").write_text(
        "from pathlib import Path\nprint(Path('src/app.py').read_text().count('VALUE = 2'))\n",
        encoding="utf-8",
    )
    (tmp_path / "worker.py").write_text(
        "from pathlib import Path\nPath('src/app.py').write_text('VALUE = 1\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)

    config = base_config(tmp_path)
    config["agent"]["command"] = f"{sys.executable} worker.py"
    run = run_loop(config)

    assert run["accepted_count"] == 1
    assert run["rejected_count"] == 0
    assert run["final_score"] == 0
    assert run["iterations"][0]["commit"]


def test_loop_reverts_rejected_iteration(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "metric.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "worker.py").write_text(
        "from pathlib import Path\nPath('src/app.py').write_text('LIVE_TRADING=true\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)

    config = base_config(tmp_path)
    config["agent"]["command"] = f"{sys.executable} worker.py"
    run = run_loop(config)

    assert run["accepted_count"] == 0
    assert run["rejected_count"] == 1
    assert "LIVE_TRADING=true" not in (tmp_path / "src" / "app.py").read_text(encoding="utf-8")
