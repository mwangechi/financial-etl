"""
API Data Extractor.

Fetches financial market data from external APIs with retry logic,
rate limiting, and structured error handling.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger("financial_etl.extract")


# ---------------------------------------------------------------------------
# Extractor Interface
# ---------------------------------------------------------------------------


class BaseExtractor(ABC):
    """Abstract base class for all data extractors."""

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """Extract data and return as a DataFrame."""
        ...

    @abstractmethod
    def validate_response(self, data: Any) -> bool:
        """Validate that the API response is usable."""
        ...


# ---------------------------------------------------------------------------
# Alpha Vantage Stock Extractor
# ---------------------------------------------------------------------------


class StockPriceExtractor(BaseExtractor):
    """Extracts daily stock price data from Alpha Vantage API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        symbols: list[str],
        function: str = "TIME_SERIES_DAILY",
        output_size: str = "compact",
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_per_minute: int = 5,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.symbols = symbols
        self.function = function
        self.output_size = output_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = 60.0 / rate_limit_per_minute

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_symbol(self, symbol: str) -> dict:
        """Fetch data for a single symbol with retries."""
        params = {
            "function": self.function,
            "symbol": symbol,
            "apikey": self.api_key,
            "outputsize": self.output_size,
        }

        logger.info("Fetching %s data for %s", self.function, symbol)
        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()

        if "Error Message" in data:
            raise ValueError(f"API error for {symbol}: {data['Error Message']}")

        if "Note" in data:
            logger.warning("API rate limit note: %s", data["Note"])
            time.sleep(60)  # Back off on rate limit
            raise requests.ConnectionError("Rate limited, retrying...")

        return data

    def validate_response(self, data: dict) -> bool:
        """Check that the response contains time series data."""
        time_series_key = "Time Series (Daily)"
        if time_series_key not in data:
            logger.error("Response missing '%s' key", time_series_key)
            return False
        if len(data[time_series_key]) == 0:
            logger.error("Time series data is empty")
            return False
        return True

    def _parse_time_series(self, data: dict, symbol: str) -> pd.DataFrame:
        """Parse the API response into a clean DataFrame."""
        time_series_key = "Time Series (Daily)"
        ts_data = data[time_series_key]

        records = []
        for date_str, values in ts_data.items():
            record = {
                "date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                "symbol": symbol,
            }
            record.update(values)
            records.append(record)

        df = pd.DataFrame(records)
        logger.info("Parsed %d records for %s", len(df), symbol)
        return df

    def extract(self) -> pd.DataFrame:
        """Extract daily prices for all configured symbols."""
        all_frames: list[pd.DataFrame] = []

        for i, symbol in enumerate(self.symbols):
            if i > 0:
                logger.debug("Rate limit delay: %.1fs", self.rate_limit_delay)
                time.sleep(self.rate_limit_delay)

            try:
                raw_data = self._fetch_symbol(symbol)

                if not self.validate_response(raw_data):
                    logger.warning("Skipping %s — invalid response", symbol)
                    continue

                df = self._parse_time_series(raw_data, symbol)
                all_frames.append(df)

            except Exception as exc:
                logger.error("Failed to extract %s: %s", symbol, exc)
                continue

        if not all_frames:
            logger.warning("No data extracted for any symbol")
            return pd.DataFrame()

        combined = pd.concat(all_frames, ignore_index=True)
        logger.info("Total extracted: %d records across %d symbols", len(combined), len(all_frames))
        return combined


# ---------------------------------------------------------------------------
# Forex Extractor
# ---------------------------------------------------------------------------


class ForexExtractor(BaseExtractor):
    """Extracts daily forex rate data from Alpha Vantage API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        pairs: list[dict[str, str]],
        output_size: str = "compact",
        timeout: int = 30,
        rate_limit_per_minute: int = 5,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.pairs = pairs
        self.output_size = output_size
        self.timeout = timeout
        self.rate_limit_delay = 60.0 / rate_limit_per_minute

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_pair(self, from_currency: str, to_currency: str) -> dict:
        """Fetch forex data for a single currency pair."""
        params = {
            "function": "FX_DAILY",
            "from_symbol": from_currency,
            "to_symbol": to_currency,
            "apikey": self.api_key,
            "outputsize": self.output_size,
        }

        logger.info("Fetching FX %s/%s", from_currency, to_currency)
        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def validate_response(self, data: dict) -> bool:
        """Check the response has forex time series data."""
        key = "Time Series FX (Daily)"
        return key in data and len(data[key]) > 0

    def extract(self) -> pd.DataFrame:
        """Extract forex data for all configured pairs."""
        all_frames: list[pd.DataFrame] = []

        for i, pair in enumerate(self.pairs):
            if i > 0:
                time.sleep(self.rate_limit_delay)

            try:
                raw = self._fetch_pair(pair["from"], pair["to"])

                if not self.validate_response(raw):
                    logger.warning("Skipping %s/%s — invalid response", pair["from"], pair["to"])
                    continue

                ts = raw["Time Series FX (Daily)"]
                records = []
                for date_str, values in ts.items():
                    record = {
                        "date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                        "pair": f"{pair['from']}/{pair['to']}",
                    }
                    record.update(values)
                    records.append(record)

                df = pd.DataFrame(records)
                all_frames.append(df)
                logger.info("Parsed %d FX records for %s/%s", len(df), pair["from"], pair["to"])

            except Exception as exc:
                logger.error("Failed FX %s/%s: %s", pair["from"], pair["to"], exc)
                continue

        if not all_frames:
            return pd.DataFrame()

        return pd.concat(all_frames, ignore_index=True)
