# Contributing

Keep this project small, auditable, and safe by default.

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
python scripts/hermes_autoresearch.py --config examples/autoresearch.generic-python.yaml --dry-run
```

## Safety Expectations

- Do not add live trading execution.
- Do not add order placement behavior.
- Do not weaken forbidden path or forbidden pattern checks without tests.
- Do not require heavy runtime frameworks.
- Keep worker execution, scoring, safety, and reporting behavior easy to inspect.

## Pull Request Checklist

- Tests pass with `pytest -q`.
- The generic dry-run command succeeds.
- New safety behavior has unit coverage.
- Public docs are updated when behavior changes.
