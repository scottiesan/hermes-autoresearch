import pytest

from scripts.hermes_autoresearch_score import (
    CommandResult,
    ScoreError,
    improved,
    parse_failing_tests,
    parse_score,
)


def test_failing_tests_parser_reads_pytest_summary():
    output = "FAILED tests/test_a.py::test_x\n= 2 failed, 3 passed in 0.12s ="
    assert parse_failing_tests(output) == 2


def test_failing_tests_parser_returns_zero_when_no_failure_detected():
    assert parse_failing_tests("===== 7 passed in 0.20s =====") == 0


def test_numeric_stdout_parser_accepts_one_float():
    result = CommandResult(returncode=0, stdout="latency_ms 12.5\n")
    assert parse_score("numeric_stdout", result) == 12.5


def test_numeric_stdout_parser_rejects_multiple_numbers():
    result = CommandResult(returncode=0, stdout="before 1 after 2")
    with pytest.raises(ScoreError):
        parse_score("numeric_stdout", result)


def test_grep_count_parser():
    assert parse_score("grep_count", CommandResult(0, "42\n", "")) == 42


def test_exit_code_parser():
    assert parse_score("exit_code", CommandResult(0, "", "")) == 0
    assert parse_score("exit_code", CommandResult(1, "", "")) == 1


def test_improvement_comparison_lower_and_higher():
    assert improved(5, 4, "lower") is True
    assert improved(5, 6, "lower") is False
    assert improved(5, 6, "higher") is True
    assert improved(5, 4, "higher") is False
