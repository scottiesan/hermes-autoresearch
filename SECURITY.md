# Security

Hermes Autoresearch runs metric, verify, and guard shell commands from YAML configuration files and asks a local code agent to edit repositories. Treat configs as trusted code and review them before every production run.

## Reporting

For public releases, report security issues through the repository's private vulnerability reporting feature if enabled, or open a minimal issue that avoids sensitive details.

## Safety Model

The supervisor is designed to reject changes that touch configured forbidden paths, add configured forbidden patterns, fail guard checks, or modify files outside scope.

Production usage should keep `safety.require_clean_git: true`, use a narrow `scope`, and keep `loop.max_iterations` low until the metric and guard commands are stable.

The default trading guardrails must not be weakened:

- Never enable live execution.
- Never place orders.
- Never modify `.env`, secrets, private keys, wallets, broker credentials, or production execution configs.
