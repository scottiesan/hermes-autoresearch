# Hermes Autoresearch

Hermes Autoresearch is a CLI-first supervisor loop for measurable engineering goals, built for [Nous Research Hermes Agent](https://github.com/nousresearch/hermes-agent). Hermes owns the run, safety checks, scoring, commits, reverts, and logs. Codex CLI is used as a worker that makes exactly one atomic code change per iteration.

Status: beta. The CLI and installer are covered by unit and config-driven integration tests, and CI runs against Python 3.10 through 3.13.

The loop is:

1. Load and validate YAML config.
2. Require a clean target git repository unless disabled.
3. Create a new branch.
4. Establish a baseline metric.
5. Generate an iteration prompt for Codex CLI.
6. Run verify and guard commands.
7. Score the result.
8. Accept and commit only if the score improves and safety passes.
9. Revert rejected changes.
10. Write JSON and Markdown logs under `autoresearch-results/`.

## Default Install

For most Hermes Agent users, install the skill directly from GitHub with `pipx`:

```bash
pipx run --spec git+https://github.com/scottiesan/hermes-autoresearch hermes-autoresearch-install-skill --profile coder --category software-development
```

This copies the bundled skill into:

```text
~/.hermes/profiles/coder/skills/software-development/hermes-autoresearch
```

Restart Hermes after installation so the `coder` profile reloads skills.

## Sample Usage Inside Hermes

After installing the skill, ask Hermes:

```text
Use hermes-autoresearch on my repo. Goal: reduce failing pytest tests. Start with one dry-run plan, then run one iteration only if the repo is clean.
```

For a specific config:

```text
Use hermes-autoresearch with /path/to/autoresearch.yaml. Verify the plan first, then run the supervised loop.
```

For a trading harness:

```text
Use hermes-autoresearch with examples/autoresearch.trading-harness.yaml. Keep the run paper-only; never enable live execution or order placement.
```

## Generic Example

```bash
python -m pip install -e ".[dev]"
python scripts/hermes_autoresearch.py --config examples/autoresearch.generic-python.yaml --dry-run
python scripts/hermes_autoresearch.py run --config examples/autoresearch.generic-python.yaml
python scripts/hermes_autoresearch.py report --config examples/autoresearch.generic-python.yaml
```

The generic config uses `pytest -q`, the `failing_tests` parser, and a `python -m compileall .` guard.

## Installing The Hermes Skill

The default install path is the `pipx` command above. From a cloned checkout:

```bash
python scripts/install_hermes_skill.py --profile coder --category software-development
```

From the public GitHub URL:

```bash
python scripts/install_hermes_skill.py \
  --source https://github.com/scottiesan/hermes-autoresearch \
  --profile coder \
  --category software-development
```

The installer copies `.hermes/skills/hermes-autoresearch` into:

```text
~/.hermes/profiles/<profile>/skills/<category>/hermes-autoresearch
```

Use `--dry-run` to preview and `--overwrite` to replace an existing install with a timestamped backup.

If the Python package is installed, this also works from any directory. The installer will clone the public repo automatically when the current working directory is not a checkout:

```bash
hermes-autoresearch-install-skill --profile coder --category software-development
```

## Trading Harness Example

```bash
python scripts/hermes_autoresearch.py plan --config examples/autoresearch.trading-harness.yaml
python scripts/hermes_autoresearch.py run --config examples/autoresearch.trading-harness.yaml
```

The trading example is scoped to the paper-trading harness, tests, and scripts. Its safety settings reject live execution flags, order placement calls, secrets, keys, wallet files, and `.env` changes.

## Config Notes

Supported metric parsers:

- `failing_tests`: parses pytest output and returns the number of failed tests.
- `grep_count`: expects stdout to be one integer.
- `numeric_stdout`: expects stdout to contain exactly one integer or float.
- `exit_code`: maps exit code `0` to score `0` and nonzero to score `1`.

Supported directions:

- `lower`: accept smaller scores.
- `higher`: accept larger scores.

Production config rules:

- `repo_path` must point at an existing git repository for real runs.
- `results.dir` must be a relative path inside `repo_path`.
- `scope`, `safety.forbid_paths`, and `safety.forbid_patterns` must be explicit string lists.
- `agent.timeout_seconds` and `loop.max_iterations` must be positive integers.
- `agent.command` is parsed as argv and receives the worker prompt on stdin.
- `metric.command`, `verify.command`, and `guard.command` execute through the local shell and must be treated as trusted code.

## Production Checklist

- CI is passing on the target commit.
- The target repo is clean before starting.
- The config has been reviewed by a human.
- `loop.max_iterations` starts at `1` for new repositories.
- The guard command checks for project-specific safety invariants.
- Trading repos include live-execution and order-placement forbidden patterns.
- Accepted commits are reviewed before merging to a protected branch.

## Limitations

- This is intentionally not an MCP server.
- Config commands execute through the local shell, so configs should be reviewed before running.
- The Codex worker command must be available locally for non-dry runs.
- Scoring is command-output based and should be deterministic.

## Public Release Checklist

- `python scripts/hermes_autoresearch.py --config examples/autoresearch.generic-python.yaml --dry-run`
- `pytest -q`
- Confirm `.hermes/skills/hermes-autoresearch/SKILL.md` has valid frontmatter.
- Confirm examples do not include secrets or live execution flags.
- Confirm docs state that trading runs must remain paper-only.
