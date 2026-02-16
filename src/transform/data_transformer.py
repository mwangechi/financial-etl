"""
Data Transformer.

Applies column renaming, type casting, and derived column
calculations to extracted financial data.
"""

import logging
from typing import Any

import pandas as pd
import numpy as np

logger = logging.getLogger("financial_etl.transform")


class DataTransformer:
    """Transforms raw extracted data into analysis-ready format."""

    def __init__(self, transform_config: dict[str, Any]) -> None:
        """
        Args:
            transform_config: Transform rules from etl_config.yaml.
        """
        self.config = transform_config

    def rename_columns(self, df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
        """Rename columns according to the mapping."""
        renamed = df.rename(columns=mapping)
        logger.debug("Renamed %d columns", len(mapping))
        return renamed

    def cast_numeric_columns(
        self, df: pd.DataFrame, columns: list[str]
    ) -> pd.DataFrame:
        """Cast specified columns to float64, coercing errors to NaN."""
        for col in columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        logger.debug("Cast %d columns to numeric", len(columns))
        return df

    def add_derived_columns(
        self, df: pd.DataFrame, derived: dict[str, str]
    ) -> pd.DataFrame:
        """
        Add derived columns using safe expression evaluation.

        Expressions reference existing column names and support
        basic arithmetic: +, -, *, /, ().
        """
        for col_name, expression in derived.items():
            try:
                # Build a safe locals dict with only the DataFrame columns
                col_locals = {c: df[c] for c in df.columns if c in expression}
                col_locals["np"] = np
                df[col_name] = eval(expression, {"__builtins__": {}}, col_locals)  # noqa: S307
                logger.debug("Added derived column: %s", col_name)
            except Exception as exc:
                logger.error("Failed to compute '%s': %s", col_name, exc)
                df[col_name] = np.nan
        return df

    def clean_dates(self, df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
        """Ensure date column is proper datetime type."""
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        return df

    def drop_duplicates(
        self, df: pd.DataFrame, subset: list[str] | None = None
    ) -> pd.DataFrame:
        """Remove duplicate rows, keeping first occurrence."""
        before = len(df)
        df = df.drop_duplicates(subset=subset, keep="first")
        dropped = before - len(df)
        if dropped > 0:
            logger.info("Dropped %d duplicate rows", dropped)
        return df

    def transform_stock_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """Full transformation pipeline for daily stock price data."""
        config = self.config.get("daily_stock_prices", {})

        # 1) Rename raw API columns
        rename_map = config.get("rename_columns", {})
        if rename_map:
            df = self.rename_columns(df, rename_map)

        # 2) Cast price/volume to numeric
        numeric_cols = ["open_price", "high_price", "low_price", "close_price", "volume"]
        df = self.cast_numeric_columns(df, numeric_cols)

        # 3) Clean dates
        df = self.clean_dates(df)

        # 4) Derived columns
        derived = config.get("derived_columns", {})
        if derived:
            df = self.add_derived_columns(df, derived)

        # 5) Round floats
        float_cols = df.select_dtypes(include=["float64"]).columns
        df[float_cols] = df[float_cols].round(6)

        # 6) Dedup
        df = self.drop_duplicates(df, subset=["date", "symbol"])

        # 7) Sort
        df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

        logger.info("Transformed stock data: %d rows, %d columns", len(df), len(df.columns))
        return df

    def transform_forex_rates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Full transformation pipeline for forex rate data."""
        config = self.config.get("forex_rates", {})

        rename_map = config.get("rename_columns", {})
        if rename_map:
            df = self.rename_columns(df, rename_map)

        numeric_cols = ["open_rate", "high_rate", "low_rate", "close_rate"]
        df = self.cast_numeric_columns(df, numeric_cols)
        df = self.clean_dates(df)
        df = self.drop_duplicates(df, subset=["date", "pair"])
        df = df.sort_values(["pair", "date"]).reset_index(drop=True)

        logger.info("Transformed forex data: %d rows, %d columns", len(df), len(df.columns))
        return df
