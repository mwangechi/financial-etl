"""Tests for the API extractor."""

import pytest
import responses
import json
from datetime import date

from src.extract.api_extractor import StockPriceExtractor, ForexExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_STOCK_RESPONSE = {
    "Meta Data": {
        "1. Information": "Daily Prices",
        "2. Symbol": "AAPL",
    },
    "Time Series (Daily)": {
        "2025-01-10": {
            "1. open": "150.00",
            "2. high": "155.00",
            "3. low": "149.00",
            "4. close": "153.50",
            "5. volume": "50000000",
        },
        "2025-01-09": {
            "1. open": "148.00",
            "2. high": "152.00",
            "3. low": "147.50",
            "4. close": "150.00",
            "5. volume": "45000000",
        },
    },
}

MOCK_FOREX_RESPONSE = {
    "Meta Data": {"1. Information": "Forex Daily"},
    "Time Series FX (Daily)": {
        "2025-01-10": {
            "1. open": "1.0850",
            "2. high": "1.0900",
            "3. low": "1.0800",
            "4. close": "1.0875",
        },
    },
}


# ---------------------------------------------------------------------------
# Stock Extractor Tests
# ---------------------------------------------------------------------------


class TestStockPriceExtractor:
    @responses.activate
    def test_extract_single_symbol(self):
        """Extracts and parses data for one symbol."""
        responses.add(
            responses.GET,
            "https://api.test.com/query",
            json=MOCK_STOCK_RESPONSE,
            status=200,
        )

        extractor = StockPriceExtractor(
            base_url="https://api.test.com/query",
            api_key="test_key",
            symbols=["AAPL"],
            rate_limit_per_minute=60,
        )

        df = extractor.extract()

        assert len(df) == 2
        assert "symbol" in df.columns
        assert "date" in df.columns
        assert df["symbol"].unique().tolist() == ["AAPL"]

    @responses.activate
    def test_extract_handles_api_error(self):
        """Gracefully handles API error responses."""
        responses.add(
            responses.GET,
            "https://api.test.com/query",
            json={"Error Message": "Invalid API call"},
            status=200,
        )

        extractor = StockPriceExtractor(
            base_url="https://api.test.com/query",
            api_key="bad_key",
            symbols=["INVALID"],
            rate_limit_per_minute=60,
        )

        df = extractor.extract()
        assert df.empty

    def test_validate_response_valid(self):
        """validate_response returns True for valid data."""
        extractor = StockPriceExtractor(
            base_url="https://api.test.com/query",
            api_key="key",
            symbols=[],
        )
        assert extractor.validate_response(MOCK_STOCK_RESPONSE) is True

    def test_validate_response_missing_key(self):
        """validate_response returns False when time series key is missing."""
        extractor = StockPriceExtractor(
            base_url="https://api.test.com/query",
            api_key="key",
            symbols=[],
        )
        assert extractor.validate_response({"Meta Data": {}}) is False


# ---------------------------------------------------------------------------
# Forex Extractor Tests
# ---------------------------------------------------------------------------


class TestForexExtractor:
    @responses.activate
    def test_extract_forex_pair(self):
        """Extracts and parses forex data for one pair."""
        responses.add(
            responses.GET,
            "https://api.test.com/query",
            json=MOCK_FOREX_RESPONSE,
            status=200,
        )

        extractor = ForexExtractor(
            base_url="https://api.test.com/query",
            api_key="test_key",
            pairs=[{"from": "EUR", "to": "USD"}],
            rate_limit_per_minute=60,
        )

        df = extractor.extract()

        assert len(df) == 1
        assert "pair" in df.columns
        assert df["pair"].iloc[0] == "EUR/USD"

    def test_validate_response_valid(self):
        """validate_response returns True for valid forex data."""
        extractor = ForexExtractor(
            base_url="https://api.test.com/query",
            api_key="key",
            pairs=[],
        )
        assert extractor.validate_response(MOCK_FOREX_RESPONSE) is True
