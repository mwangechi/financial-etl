"""
Data Quality Validators.

Provides composable validation checks that can be applied to
DataFrames before loading. Each check returns a report with
pass/fail status and details.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger("financial_etl.quality")


# ---------------------------------------------------------------------------
# Validation Result
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check_name: str
    passed: bool
    details: str = ""
    failing_rows: int = 0


@dataclass
class ValidationReport:
    """Aggregated report of all validation checks."""

    results: list[ValidationResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def summary(self) -> str:
        lines = [f"Validation Report — {len(self.results)} checks"]
        for r in self.results:
            status = "✓ PASS" if r.passed else "✗ FAIL"
            lines.append(f"  {status} | {r.check_name}: {r.details}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Individual Validators
# ---------------------------------------------------------------------------


def check_not_null(df: pd.DataFrame, columns: list[str]) -> ValidationResult:
    """Ensure specified columns contain no NULL values."""
    null_counts = df[columns].isnull().sum()
    failing = null_counts[null_counts > 0]

    if len(failing) == 0:
        return ValidationResult(
            check_name="not_null",
            passed=True,
            details=f"All {len(columns)} columns have no nulls",
        )

    detail_parts = [f"{col}={count}" for col, count in failing.items()]
    return ValidationResult(
        check_name="not_null",
        passed=False,
        details=f"Nulls found: {', '.join(detail_parts)}",
        failing_rows=int(failing.sum()),
    )


def check_range(
    df: pd.DataFrame,
    column: str,
    min_val: float | None = None,
    max_val: float | None = None,
) -> ValidationResult:
    """Ensure column values fall within [min_val, max_val]."""
    series = pd.to_numeric(df[column], errors="coerce")
    violations = pd.Series([False] * len(df))

    if min_val is not None:
        violations = violations | (series < min_val)
    if max_val is not None:
        violations = violations | (series > max_val)

    fail_count = int(violations.sum())

    if fail_count == 0:
        return ValidationResult(
            check_name=f"range({column})",
            passed=True,
            details=f"{column} within [{min_val}, {max_val}]",
        )

    return ValidationResult(
        check_name=f"range({column})",
        passed=False,
        details=f"{fail_count} values outside [{min_val}, {max_val}]",
        failing_rows=fail_count,
    )


def check_unique_composite(
    df: pd.DataFrame, columns: list[str]
) -> ValidationResult:
    """Ensure the combination of columns is unique (no duplicates)."""
    dupes = df.duplicated(subset=columns, keep=False)
    dupe_count = int(dupes.sum())

    if dupe_count == 0:
        return ValidationResult(
            check_name=f"unique({'+'.join(columns)})",
            passed=True,
            details="No duplicate composite keys",
        )

    return ValidationResult(
        check_name=f"unique({'+'.join(columns)})",
        passed=False,
        details=f"{dupe_count} duplicate rows on {'+'.join(columns)}",
        failing_rows=dupe_count,
    )


def check_schema(
    df: pd.DataFrame, expected_columns: list[str]
) -> ValidationResult:
    """Ensure the DataFrame has all expected columns."""
    missing = set(expected_columns) - set(df.columns)

    if not missing:
        return ValidationResult(
            check_name="schema",
            passed=True,
            details=f"All {len(expected_columns)} expected columns present",
        )

    return ValidationResult(
        check_name="schema",
        passed=False,
        details=f"Missing columns: {', '.join(sorted(missing))}",
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_quality_checks(
    df: pd.DataFrame, checks_config: list[dict[str, Any]]
) -> ValidationReport:
    """
    Run all configured quality checks against a DataFrame.

    Args:
        df: The data to validate.
        checks_config: List of check definitions from etl_config.yaml.

    Returns:
        A ValidationReport with results for each check.
    """
    report = ValidationReport()

    for check in checks_config:
        check_type = check["type"]

        if check_type == "not_null":
            result = check_not_null(df, check["columns"])
        elif check_type == "range":
            result = check_range(
                df,
                check["column"],
                min_val=check.get("min"),
                max_val=check.get("max"),
            )
        elif check_type == "unique_composite":
            result = check_unique_composite(df, check["columns"])
        elif check_type == "schema":
            result = check_schema(df, check["columns"])
        else:
            logger.warning("Unknown check type: %s", check_type)
            continue

        report.results.append(result)

    logger.info(report.summary())
    return report
