"""Tests for the data transformer."""

import pytest
import pandas as pd
import numpy as np
from datetime import date

from src.transform.data_transformer import DataTransformer


@pytest.fixture
def transformer():
    """Create a transformer with stock config."""
    config = {
        "daily_stock_prices": {
            "rename_columns": {
                "1. open": "open_price",
                "2. high": "high_price",
                "3. low": "low_price",
                "4. close": "close_price",
                "5. volume": "volume",
            },
            "derived_columns": {
                "daily_return": "(close_price - open_price) / open_price",
                "price_range": "high_price - low_price",
            },
        },
        "forex_rates": {
            "rename_columns": {
                "1. open": "open_rate",
                "2. high": "high_rate",
                "3. low": "low_rate",
                "4. close": "close_rate",
            },
        },
    }
    return DataTransformer(config)


@pytest.fixture
def raw_stock_df():
    """Create a raw stock DataFrame mimicking API output."""
    return pd.DataFrame([
        {
            "date": date(2025, 1, 10),
            "symbol": "AAPL",
            "1. open": "150.00",
            "2. high": "155.00",
            "3. low": "149.00",
            "4. close": "153.50",
            "5. volume": "50000000",
        },
        {
            "date": date(2025, 1, 9),
            "symbol": "AAPL",
            "1. open": "148.00",
            "2. high": "152.00",
            "3. low": "147.50",
            "4. close": "150.00",
            "5. volume": "45000000",
        },
    ])


class TestRenameColumns:
    def test_renames_correctly(self, transformer):
        df = pd.DataFrame({"1. open": [1], "2. high": [2]})
        mapping = {"1. open": "open_price", "2. high": "high_price"}
        result = transformer.rename_columns(df, mapping)
        assert "open_price" in result.columns
        assert "high_price" in result.columns


class TestCastNumericColumns:
    def test_casts_string_to_float(self, transformer):
        df = pd.DataFrame({"price": ["100.50", "200.75"]})
        result = transformer.cast_numeric_columns(df, ["price"])
        assert result["price"].dtype == np.float64

    def test_coerces_invalid_to_nan(self, transformer):
        df = pd.DataFrame({"price": ["100.50", "invalid"]})
        result = transformer.cast_numeric_columns(df, ["price"])
        assert pd.isna(result["price"].iloc[1])


class TestTransformStockPrices:
    def test_full_transform(self, transformer, raw_stock_df):
        result = transformer.transform_stock_prices(raw_stock_df)

        # Columns renamed
        assert "open_price" in result.columns
        assert "1. open" not in result.columns

        # Derived columns added
        assert "daily_return" in result.columns
        assert "price_range" in result.columns

        # Sorted by symbol, date
        assert result["date"].iloc[0] < result["date"].iloc[1]

    def test_deduplication(self, transformer, raw_stock_df):
        duplicated = pd.concat([raw_stock_df, raw_stock_df], ignore_index=True)
        result = transformer.transform_stock_prices(duplicated)
        assert len(result) == 2


class TestDropDuplicates:
    def test_removes_dupes(self, transformer):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})
        result = transformer.drop_duplicates(df, subset=["a"])
        assert len(result) == 2
