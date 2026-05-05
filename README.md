# Hermes Autoresearch

Hermes Autoresearch is a CLI-first supervisor for measurable engineering improvement loops. Hermes supervises the run, Codex CLI acts as the worker, and git is used to retain improvements while reverting failed attempts.

The loop is:

1. Establish a baseline metric.
2. Ask Codex CLI to make one atomic change.
3. Run verify and guard commands.
4. Score the result.
5. Commit accepted improvements.
6. Revert rejected changes.
7. Write run logs under `autoresearch-results/`.

This project is inspired by `codex-autoresearch`, but is designed to be Hermes-native and deliberately starts as a CLI plus Hermes skill. It does not include an MCP server yet.

## Install

```bash
python -m pip install -e ".[dev]"
```

Only PyYAML is required at runtime. Pytest is used for tests.

## Quick Check

```bash
python scripts/hermes_autoresearch.py --config examples/autoresearch.generic-python.yaml --dry-run
pytest -q
```

## CLI Usage

```bash
python scripts/hermes_autoresearch.py plan --config examples/autoresearch.generic-python.yaml
python scripts/hermes_autoresearch.py run --config autoresearch.yaml
python scripts/hermes_autoresearch.py report --config autoresearch.yaml
```

For real runs, the configured `repo_path` must be a git repository. By default the working tree must be clean before the supervisor creates an autoresearch branch.

## Hermes Skill

The Hermes skill lives at:

```text
.hermes/skills/hermes-autoresearch/SKILL.md
```

Install it into a Hermes profile with your Hermes skill installer, for example:

```bash
python3 /path/to/install_profile_skill.py \
  --source .hermes/skills/hermes-autoresearch \
  --profile coder \
  --category software-development
```

After installing, restart Hermes or Codex so the profile reloads skills.

## Safety Defaults

The supervisor rejects changes that:

- Modify forbidden paths such as `.env`, private keys, wallet files, or `secrets/`.
- Add forbidden patterns such as `EXECUTION_ENABLED=true`, `LIVE_TRADING=true`, or order placement calls.
- Touch files outside configured scope unless explicitly allowed.
- Produce no code changes.
- Fail guard checks.
- Cannot be scored.

Trading hard rule: never enable live execution and never place orders.

## Examples

- `examples/autoresearch.generic-python.yaml`: generic Python test-improvement loop.
- `examples/autoresearch.trading-harness.yaml`: paper-trading harness loop with stricter trading guardrails.

See [docs/hermes-autoresearch.md](docs/hermes-autoresearch.md) for the full workflow and config notes.
