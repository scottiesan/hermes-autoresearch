"""Metric parsing and score comparison for Hermes autoresearch."""

from __future__ import annotations

import re
from dataclasses import dataclass


class ScoreError(ValueError):
    """Raised when a metric output cannot be converted into a score."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part)


def parse_score(parser: str, result: CommandResult) -> float:
    """Parse a command result with a named parser."""
    parser = parser.strip()
    if parser == "failing_tests":
        return float(parse_failing_tests(result.combined_output))
    if parser == "grep_count":
        return float(parse_grep_count(result.stdout))
    if parser == "numeric_stdout":
        return float(parse_numeric_stdout(result.stdout))
    if parser == "exit_code":
        return 0.0 if result.returncode == 0 else 1.0
    raise ScoreError(f"unknown metric parser: {parser}")


def parse_failing_tests(output: str) -> int:
    """Return failed pytest test count from pytest output."""
    patterns = [
        r"=+\s*(\d+)\s+failed\b",
        r"\bFAILED\s+.*?::",
        r"\bfailed=(\d+)\b",
    ]
    summary_match = re.search(patterns[0], output, flags=re.IGNORECASE)
    if summary_match:
        return int(summary_match.group(1))

    failed_lines = re.findall(patterns[1], output)
    if failed_lines:
        return len(failed_lines)

    junit_like = re.search(patterns[2], output, flags=re.IGNORECASE)
    if junit_like:
        return int(junit_like.group(1))

    return 0


def parse_grep_count(output: str) -> int:
    text = output.strip()
    if not re.fullmatch(r"[+-]?\d+", text):
        raise ScoreError(f"grep_count expected an integer, got: {text!r}")
    return int(text)


def parse_numeric_stdout(output: str) -> float:
    matches = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", output)
    if len(matches) != 1:
        raise ScoreError(f"numeric_stdout expected exactly one number, found {len(matches)}")
    value = float(matches[0])
    return int(value) if value.is_integer() else value


def improved(before: float, after: float, direction: str) -> bool:
    if direction == "lower":
        return after < before
    if direction == "higher":
        return after > before
    raise ScoreError(f"direction must be lower or higher, got: {direction}")
