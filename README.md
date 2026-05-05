# Hermes Autoresearch

Hermes Autoresearch is a CLI-first supervisor for measurable engineering improvement loops, built for [Nous Research Hermes Agent](https://github.com/nousresearch/hermes-agent). Hermes supervises the run, Codex CLI acts as the worker, and git is used to retain improvements while reverting failed attempts.

The loop is:

1. Establish a baseline metric.
2. Ask Codex CLI to make one atomic change.
3. Run verify and guard commands.
4. Score the result.
5. Commit accepted improvements.
6. Revert rejected changes.
7. Write run logs under `autoresearch-results/`.

This project is inspired by `codex-autoresearch`, but is designed to be Hermes-native for `nousresearch/hermes-agent` and deliberately starts as a CLI plus Hermes skill. It does not include an MCP server yet.

## Install The Hermes Skill

Default one-command install for Hermes Agent:

```bash
pipx run --spec git+https://github.com/scottiesan/hermes-autoresearch hermes-autoresearch-install-skill --profile coder --category software-development
```

This copies the bundled skill into:

```text
~/.hermes/profiles/coder/skills/software-development/hermes-autoresearch
```

Restart Hermes after installation so the profile reloads skills.

## Sample Usage Inside Hermes

After installing the skill, ask Hermes:

```text
Use hermes-autoresearch on my repo. Goal: reduce failing pytest tests. Start with one dry-run plan, then run one iteration only if the repo is clean.
```

For a config-driven run:

```text
Use hermes-autoresearch with /path/to/autoresearch.yaml. Verify the plan first, then run the supervised loop.
```

Hermes should act as the supervisor. Codex CLI is only the worker that makes one atomic change per iteration.

## Developer Install

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

The easiest install path is the `pipx` command at the top of this README. From a cloned checkout, you can also run:

```bash
python scripts/install_hermes_skill.py \
  --profile coder \
  --category software-development
```

Or point the installer at the public repo URL:

```bash
python scripts/install_hermes_skill.py \
  --source https://github.com/scottiesan/hermes-autoresearch \
  --profile coder \
  --category software-development
```

If installed as a Python package, use the console script. When run outside a clone, it automatically pulls the skill from this public repo:

```bash
hermes-autoresearch-install-skill --profile coder --category software-development
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
