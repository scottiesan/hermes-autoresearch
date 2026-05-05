# Hermes Autoresearch

Hermes Autoresearch is a CLI-first supervisor loop for measurable engineering goals. Hermes owns the run, safety checks, scoring, commits, reverts, and logs. Codex CLI is used as a worker that makes exactly one atomic code change per iteration.

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

## Generic Example

```bash
python -m pip install -e ".[dev]"
python scripts/hermes_autoresearch.py --config examples/autoresearch.generic-python.yaml --dry-run
python scripts/hermes_autoresearch.py run --config examples/autoresearch.generic-python.yaml
python scripts/hermes_autoresearch.py report --config examples/autoresearch.generic-python.yaml
```

The generic config uses `pytest -q`, the `failing_tests` parser, and a `python -m compileall .` guard.

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

## Limitations

- This is intentionally not an MCP server.
- The first implementation uses shell commands from the config, so configs should be reviewed before running.
- The Codex worker command must be available locally for non-dry runs.
- Scoring is command-output based and should be deterministic.

## Public Release Checklist

- `python scripts/hermes_autoresearch.py --config examples/autoresearch.generic-python.yaml --dry-run`
- `pytest -q`
- Confirm `.hermes/skills/hermes-autoresearch/SKILL.md` has valid frontmatter.
- Confirm examples do not include secrets or live execution flags.
- Confirm docs state that trading runs must remain paper-only.
