---
name: hermes-autoresearch
description: Supervise command-verifiable autoresearch loops where Hermes manages safety, scoring, commits, and reverts while Codex CLI makes one atomic worker change per iteration.
---

# Hermes Autoresearch

Use this skill when Hermes should supervise a measurable engineering improvement loop and Codex CLI should act only as the worker code agent. Good targets include reducing failing tests, lint warnings, type errors, latency scores, grep counts, or any command-verifiable metric.

Do not use this skill for live trading, direct production execution, credential rotation, or broad product redesigns without a deterministic verification command.

## Required Inputs

- A YAML config path matching `templates/run_config.yaml`.
- A clean target git repository unless `safety.require_clean_git` is explicitly disabled.
- A metric command and parser.
- A verify command.
- A guard command.
- A scoped list of paths Codex may edit.

## Safety Rules

Hermes is the supervisor, not the code editor. Hermes should run `hermes_autoresearch`, inspect results, and decide whether another run is appropriate. Codex CLI receives one prompt per iteration and must stop after editing.

Always reject changes that:

- Modify `.env`, private keys, wallet files, broker credentials, secrets, or production execution configs.
- Add or enable `EXECUTION_ENABLED=true`, `LIVE_TRADING=true`, order placement, or live broker calls.
- Touch paths outside configured scope unless the config explicitly allows it.
- Fail the guard command.
- Produce no diff.
- Cannot be scored by the configured parser.

Trading hard rule: never enable live execution and never place orders.

## How To Run

From the project containing this skill:

```bash
python scripts/hermes_autoresearch.py plan --config examples/autoresearch.generic-python.yaml
python scripts/hermes_autoresearch.py --config examples/autoresearch.generic-python.yaml --dry-run
python scripts/hermes_autoresearch.py run --config autoresearch.yaml
python scripts/hermes_autoresearch.py report --config autoresearch.yaml
```

## Expected Outputs

The CLI writes logs under the configured `results.dir`, usually `autoresearch-results/`:

- `run.json`
- `run.md`
- `iteration-001-prompt.md`
- `iteration-001-agent.log`
- `iteration-001-verify.log`
- `iteration-001-guard.log`
- `iteration-001.diff`

## Recommended Workflow

1. Confirm the target repository and scope are correct.
2. Run `plan` or `--dry-run`.
3. Start with `loop.max_iterations: 1` for a new repo.
4. Review `run.md` and accepted commits.
5. Increase iterations only after the guard and metric behave deterministically.

## Trading Repo Warnings

For trading harnesses, keep the goal limited to tests, paper-trading reliability, static checks, parsing robustness, and compile safety. The guard must prevent live execution flags and order placement APIs. Never let an autoresearch run edit credentials, wallets, production execution configs, or broker integration secrets.
