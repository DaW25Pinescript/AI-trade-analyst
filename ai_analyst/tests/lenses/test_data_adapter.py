"""Tests for OHLCV data adapter — frozen fixture tests only.

Validates the pure transform from OHLCVResponse to lens input format.
"""

import numpy as np

from ai_analyst.api.models.market_data import Candle, OHLCVResponse
from ai_analyst.lenses.data_adapter import ohlcv_response_to_lens_input


def _make_response(candles: list[Candle]) -> OHLCVResponse:
    """Build a minimal OHLCVResponse for testing."""
    return OHLCVResponse(
        version="1.0",
        generated_at="2026-03-18T10:00:00Z",
        data_state="live",
        instrument="XAUUSD",
        timeframe="1H",
        candles=candles,
        candle_count=len(candles),
    )


SAMPLE_CANDLES = [
    Candle(timestamp=1710756000, open=2000.0, high=2010.0, low=1995.0, close=2005.0, volume=100.0),
    Candle(timestamp=1710759600, open=2005.0, high=2015.0, low=2000.0, close=2012.0, volume=150.0),
    Candle(timestamp=1710763200, open=2012.0, high=2020.0, low=2008.0, close=2018.0, volume=120.0),
]


class TestDataAdapterHappyPath:
    def test_returns_dict_with_six_keys(self):
        result = ohlcv_response_to_lens_input(_make_response(SAMPLE_CANDLES))
        expected_keys = {"timestamp", "open", "high", "low", "close", "volume"}
        assert set(result.keys()) == expected_keys

    def test_arrays_have_correct_length(self):
        result = ohlcv_response_to_lens_input(_make_response(SAMPLE_CANDLES))
        for key in result:
            assert len(result[key]) == 3, f"{key} array length mismatch"

    def test_values_are_numpy_arrays(self):
        result = ohlcv_response_to_lens_input(_make_response(SAMPLE_CANDLES))
        for key in result:
            assert isinstance(result[key], np.ndarray), f"{key} is not ndarray"

    def test_close_values_preserved(self):
        result = ohlcv_response_to_lens_input(_make_response(SAMPLE_CANDLES))
        np.testing.assert_array_almost_equal(
            result["close"], [2005.0, 2012.0, 2018.0],
        )

    def test_first_candle_values(self):
        result = ohlcv_response_to_lens_input(_make_response(SAMPLE_CANDLES))
        assert result["open"][0] == 2000.0
        assert result["high"][0] == 2010.0
        assert result["low"][0] == 1995.0
        assert result["close"][0] == 2005.0
        assert result["volume"][0] == 100.0

    def test_last_candle_values(self):
        result = ohlcv_response_to_lens_input(_make_response(SAMPLE_CANDLES))
        assert result["open"][-1] == 2012.0
        assert result["high"][-1] == 2020.0
        assert result["low"][-1] == 2008.0
        assert result["close"][-1] == 2018.0
        assert result["volume"][-1] == 120.0

    def test_timestamp_values_preserved(self):
        result = ohlcv_response_to_lens_input(_make_response(SAMPLE_CANDLES))
        np.testing.assert_array_equal(
            result["timestamp"], [1710756000, 1710759600, 1710763200],
        )


class TestDataAdapterEmptyInput:
    def test_empty_candles_returns_empty_arrays(self):
        result = ohlcv_response_to_lens_input(_make_response([]))
        for key in result:
            assert len(result[key]) == 0, f"{key} not empty"

    def test_empty_returns_all_six_keys(self):
        result = ohlcv_response_to_lens_input(_make_response([]))
        expected_keys = {"timestamp", "open", "high", "low", "close", "volume"}
        assert set(result.keys()) == expected_keys

    def test_empty_arrays_are_numpy(self):
        result = ohlcv_response_to_lens_input(_make_response([]))
        for key in result:
            assert isinstance(result[key], np.ndarray)
