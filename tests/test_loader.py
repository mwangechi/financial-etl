"""Tests for the data quality validators."""

import pytest
import pandas as pd
import numpy as np

from src.quality.validators import (
    check_not_null,
    check_range,
    check_unique_composite,
    check_schema,
    run_quality_checks,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "date": ["2025-01-10", "2025-01-09", "2025-01-08"],
        "symbol": ["AAPL", "AAPL", "MSFT"],
        "close_price": [153.5, 150.0, 280.0],
        "volume": [50_000_000, 45_000_000, 30_000_000],
    })


class TestCheckNotNull:
    def test_passes_when_no_nulls(self, sample_df):
        result = check_not_null(sample_df, ["date", "symbol"])
        assert result.passed is True

    def test_fails_when_nulls_present(self, sample_df):
        sample_df.loc[0, "symbol"] = None
        result = check_not_null(sample_df, ["symbol"])
        assert result.passed is False
        assert result.failing_rows == 1


class TestCheckRange:
    def test_passes_within_range(self, sample_df):
        result = check_range(sample_df, "close_price", min_val=0, max_val=1000)
        assert result.passed is True

    def test_fails_below_min(self, sample_df):
        sample_df.loc[0, "close_price"] = -5.0
        result = check_range(sample_df, "close_price", min_val=0)
        assert result.passed is False

    def test_fails_above_max(self, sample_df):
        result = check_range(sample_df, "close_price", max_val=100)
        assert result.passed is False
        assert result.failing_rows == 2


class TestCheckUniqueComposite:
    def test_passes_when_unique(self, sample_df):
        result = check_unique_composite(sample_df, ["date", "symbol"])
        assert result.passed is True

    def test_fails_with_duplicates(self, sample_df):
        duped = pd.concat([sample_df, sample_df.iloc[:1]], ignore_index=True)
        result = check_unique_composite(duped, ["date", "symbol"])
        assert result.passed is False


class TestCheckSchema:
    def test_passes_all_columns_present(self, sample_df):
        result = check_schema(sample_df, ["date", "symbol", "close_price"])
        assert result.passed is True

    def test_fails_missing_column(self, sample_df):
        result = check_schema(sample_df, ["date", "symbol", "missing_col"])
        assert result.passed is False
        assert "missing_col" in result.details


class TestRunQualityChecks:
    def test_full_report(self, sample_df):
        checks = [
            {"type": "not_null", "columns": ["date", "symbol"]},
            {"type": "range", "column": "close_price", "min": 0, "max": 100000},
            {"type": "unique_composite", "columns": ["date", "symbol"]},
        ]
        report = run_quality_checks(sample_df, checks)
        assert report.all_passed is True
        assert len(report.results) == 3
