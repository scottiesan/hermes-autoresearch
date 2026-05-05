# Hermes Autoresearch Worker Task

Goal:
{{ goal }}

Current score: {{ current_score }}
Metric direction: {{ metric_direction }}

Allowed scope:
{{ scope }}

Forbidden paths:
{{ forbidden_paths }}

Forbidden patterns:
{{ forbidden_patterns }}

Verify command:
`{{ verify_command }}`

Guard command:
`{{ guard_command }}`

Make exactly one atomic change that can improve the score. Never enable live trading, live execution, broker credentials, wallet access, or order placement. Do not modify .env, secrets, private keys, wallets, or production execution configs.

Stop after editing. Hermes will verify, score, commit, or revert.
