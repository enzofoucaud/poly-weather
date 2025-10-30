"""
Tests for Weather.com API client.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.clients.weather import WeatherClient


class TestWeatherClient:
    """Test suite for WeatherClient."""

    @pytest.fixture
    def client(self):
        """Create a WeatherClient instance for testing."""
        return WeatherClient(
            api_key="test_key",
            geocode="40.761,-73.864",
            location_id="KLGA:9:US"
        )

    @pytest.fixture
    def mock_forecast_response(self):
        """Mock forecast API response."""
        return {
            "calendarDayTemperatureMax": [62, 62, 58, 59, 60, 60, 60]
        }

    @pytest.fixture
    def mock_historical_response(self):
        """Mock historical API response."""
        return {
            "metadata": {
                "location_id": "KLGA:9:US",
                "units": "e"
            },
            "observations": [
                {"temp": 50, "valid_time_gmt": 1761797880},
                {"temp": 53, "valid_time_gmt": 1761801480},
                {"temp": 55, "valid_time_gmt": 1761805080},
                {"temp": 52, "valid_time_gmt": 1761808680}
            ]
        }

    def test_initialization(self, client):
        """Test client initialization."""
        assert client.api_key == "test_key"
        assert client.geocode == "40.761,-73.864"
        assert client.location_id == "KLGA:9:US"
        assert client.timeout == 10

    @patch('src.clients.weather.requests.get')
    def test_get_forecast_success(self, mock_get, client, mock_forecast_response):
        """Test successful forecast retrieval."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = mock_forecast_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Call method
        result = client.get_forecast(days=7)

        # Assertions
        assert len(result) == 7
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        assert result[today] == 62.0
        assert result[today + timedelta(days=1)] == 62.0
        assert result[today + timedelta(days=2)] == 58.0

        # Verify API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "apiKey" in call_args[1]["params"]
        assert call_args[1]["params"]["geocode"] == "40.761,-73.864"

    @patch('src.clients.weather.requests.get')
    def test_get_forecast_with_cache(self, mock_get, client, mock_forecast_response):
        """Test that forecast uses cache on subsequent calls."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = mock_forecast_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First call - should hit API
        result1 = client.get_forecast(days=7)
        assert len(result1) == 7

        # Second call - should use cache
        result2 = client.get_forecast(days=7)
        assert len(result2) == 7

        # API should only be called once
        assert mock_get.call_count == 1

    @patch('src.clients.weather.requests.get')
    def test_get_historical_today_success(self, mock_get, client, mock_historical_response):
        """Test successful historical data retrieval."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = mock_historical_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Call method
        result = client.get_historical_today()

        # Assertions
        assert result["current_max"] == 55.0  # Max of [50, 53, 55, 52]
        assert result["latest_temp"] == 52.0  # Last observation
        assert result["observation_count"] == 4
        assert len(result["observations"]) == 4

        # Verify API was called with today's date
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        today_str = datetime.now().strftime("%Y%m%d")
        assert call_args[1]["params"]["startDate"] == today_str

    @patch('src.clients.weather.requests.get')
    def test_get_historical_empty_observations(self, mock_get, client):
        """Test handling of empty observations."""
        # Setup mock with empty observations
        mock_response = Mock()
        mock_response.json.return_value = {"observations": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Call method
        result = client.get_historical_today()

        # Assertions
        assert result["current_max"] is None
        assert result["observation_count"] == 0
        assert result["latest_temp"] is None

    def test_detect_forecast_change(self, client):
        """Test forecast change detection."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        old_forecast = {
            today: 62.0,
            today + timedelta(days=1): 63.0,
            today + timedelta(days=2): 64.0
        }

        new_forecast = {
            today: 62.0,  # No change
            today + timedelta(days=1): 65.0,  # +2°F change
            today + timedelta(days=2): 64.0  # No change
        }

        changes = client.detect_forecast_change(old_forecast, new_forecast, threshold=1.0)

        # Should detect one change (day 1)
        assert len(changes) == 1
        date, old_temp, new_temp = changes[0]
        assert date == today + timedelta(days=1)
        assert old_temp == 63.0
        assert new_temp == 65.0

    def test_get_forecast_with_confidence(self, client, mock_forecast_response):
        """Test forecast with confidence scores."""
        with patch('src.clients.weather.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_forecast_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            forecasts = client.get_forecast_with_confidence(days=3)

            assert len(forecasts) == 3

            # Check confidence scores decrease with days ahead
            assert forecasts[0].confidence >= forecasts[1].confidence
            assert forecasts[1].confidence >= forecasts[2].confidence

            # J-0 should have highest confidence
            assert forecasts[0].confidence == pytest.approx(0.95, abs=0.01)

    def test_clear_cache(self, client):
        """Test cache clearing."""
        # Set cache
        client._forecast_cache = {"test": "data"}
        client._forecast_cache_time = datetime.now()

        # Clear cache
        client.clear_cache()

        # Verify cache is cleared
        assert client._forecast_cache is None
        assert client._forecast_cache_time is None

    @patch('src.clients.weather.requests.get')
    def test_request_retry_on_timeout(self, mock_get, client):
        """Test that requests are retried on timeout."""
        # First two calls timeout, third succeeds
        mock_get.side_effect = [
            Exception("Timeout"),
            Exception("Timeout"),
            Mock(json=lambda: {"calendarDayTemperatureMax": [62]}, raise_for_status=Mock())
        ]

        # Should succeed after retries
        result = client.get_forecast(days=1)
        assert len(result) == 1

        # Should have been called 3 times
        assert mock_get.call_count == 3
