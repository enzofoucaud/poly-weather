"""
Tests for Realtime Temperature Monitoring.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from src.utils.realtime_monitor import RealtimeMonitor, PositionAdjuster, TemperatureReading
from src.clients.weather import WeatherClient
from src.models.market import TemperatureMarket, PolymarketOutcome, TemperatureRange
from src.models.trade import Position


class TestRealtimeMonitor:
    """Test suite for RealtimeMonitor."""

    @pytest.fixture
    def mock_weather_client(self):
        """Create a mock weather client."""
        return Mock(spec=WeatherClient)

    @pytest.fixture
    def monitor(self, mock_weather_client):
        """Create a RealtimeMonitor instance."""
        return RealtimeMonitor(
            weather_client=mock_weather_client,
            check_interval=1
        )

    @pytest.fixture
    def sample_market(self):
        """Create a sample market for today."""
        today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)

        outcomes = [
            PolymarketOutcome(
                token_id="token_60_61",
                price=0.20,
                temperature_range=TemperatureRange.from_label("60-61°F")
            ),
            PolymarketOutcome(
                token_id="token_62_63",
                price=0.30,
                temperature_range=TemperatureRange.from_label("62-63°F")
            ),
        ]

        return TemperatureMarket(
            market_id="market_test_today",
            question="Highest temperature today?",
            target_date=today,
            outcomes=outcomes
        )

    def test_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor.check_interval == 1
        assert monitor.previous_max is None
        assert monitor.monitoring == False
        assert len(monitor.readings) == 0

    def test_is_target_day_true(self, monitor, sample_market):
        """Test target day detection when it's the target day."""
        # Sample market is set to today
        is_target = monitor.is_target_day(sample_market)

        assert is_target == True

    def test_is_target_day_false(self, monitor):
        """Test target day detection when it's not the target day."""
        tomorrow = datetime.now() + timedelta(days=1)

        market = TemperatureMarket(
            market_id="market_tomorrow",
            question="Temp tomorrow?",
            target_date=tomorrow,
            outcomes=[]
        )

        is_target = monitor.is_target_day(market)

        assert is_target == False

    def test_get_current_max_success(self, monitor, mock_weather_client):
        """Test getting current max temperature."""
        # Mock response
        mock_weather_client.get_historical_today.return_value = {
            "current_max": 62.5,
            "latest_temp": 61.0,
            "observation_count": 10
        }

        current_max = monitor.get_current_max()

        assert current_max == 62.5
        assert len(monitor.readings) == 1
        assert monitor.readings[0].current_max == 62.5

    def test_get_current_max_no_data(self, monitor, mock_weather_client):
        """Test when no temperature data is available."""
        mock_weather_client.get_historical_today.return_value = {
            "current_max": None,
            "observation_count": 0
        }

        current_max = monitor.get_current_max()

        assert current_max is None

    def test_detect_max_change_initial(self, monitor):
        """Test max change detection on first reading."""
        changed = monitor.detect_max_change(62.0)

        assert changed == False
        assert monitor.previous_max == 62.0

    def test_detect_max_change_significant(self, monitor):
        """Test detection of significant temperature change."""
        # Set initial max
        monitor.previous_max = 62.0

        # New max is 63.5°F (change of 1.5°F > threshold of 0.5°F)
        changed = monitor.detect_max_change(63.5, threshold=0.5)

        assert changed == True
        assert monitor.previous_max == 63.5

    def test_detect_max_change_insignificant(self, monitor):
        """Test when change is below threshold."""
        monitor.previous_max = 62.0

        # New max is 62.3°F (change of 0.3°F < threshold of 0.5°F)
        changed = monitor.detect_max_change(62.3, threshold=0.5)

        assert changed == False
        assert monitor.previous_max == 62.0  # Should not update

    def test_stop_monitoring(self, monitor):
        """Test stopping the monitoring loop."""
        monitor.monitoring = True

        monitor.stop_monitoring()

        assert monitor.monitoring == False

    def test_get_temperature_trend_rising(self, monitor):
        """Test trend detection for rising temperatures."""
        # Add readings showing rising trend
        now = datetime.now()
        monitor.readings = [
            TemperatureReading(now - timedelta(minutes=20), 60.0, 60.0),
            TemperatureReading(now - timedelta(minutes=15), 61.0, 61.0),
            TemperatureReading(now - timedelta(minutes=10), 62.0, 62.0),
            TemperatureReading(now - timedelta(minutes=5), 62.5, 62.5),
            TemperatureReading(now, 63.0, 63.0),
        ]

        trend = monitor.get_temperature_trend(window_minutes=30)

        assert trend == "RISING"

    def test_get_temperature_trend_falling(self, monitor):
        """Test trend detection for falling temperatures."""
        now = datetime.now()
        monitor.readings = [
            TemperatureReading(now - timedelta(minutes=20), 65.0, 65.0),
            TemperatureReading(now - timedelta(minutes=15), 64.0, 64.0),
            TemperatureReading(now - timedelta(minutes=10), 63.0, 63.0),
            TemperatureReading(now - timedelta(minutes=5), 62.5, 62.5),
            TemperatureReading(now, 62.0, 62.0),
        ]

        trend = monitor.get_temperature_trend(window_minutes=30)

        assert trend == "FALLING"

    def test_get_temperature_trend_stable(self, monitor):
        """Test trend detection for stable temperatures."""
        now = datetime.now()
        monitor.readings = [
            TemperatureReading(now - timedelta(minutes=20), 62.0, 62.0),
            TemperatureReading(now - timedelta(minutes=15), 62.2, 62.2),
            TemperatureReading(now - timedelta(minutes=10), 62.1, 62.1),
            TemperatureReading(now - timedelta(minutes=5), 62.3, 62.3),
            TemperatureReading(now, 62.0, 62.0),
        ]

        trend = monitor.get_temperature_trend(window_minutes=30)

        assert trend == "STABLE"

    def test_get_monitoring_stats_no_data(self, monitor):
        """Test stats when no readings are available."""
        stats = monitor.get_monitoring_stats()

        assert stats["status"] == "no_data"
        assert stats["num_readings"] == 0

    def test_get_monitoring_stats_with_data(self, monitor):
        """Test stats with readings."""
        now = datetime.now()
        monitor.readings = [
            TemperatureReading(now - timedelta(minutes=5), 60.0, 60.0),
            TemperatureReading(now - timedelta(minutes=3), 62.0, 62.0),
            TemperatureReading(now, 63.0, 63.0),
        ]
        monitor.monitoring = True

        stats = monitor.get_monitoring_stats()

        assert stats["status"] == "monitoring"
        assert stats["num_readings"] == 3
        assert stats["current_max"] == 63.0
        assert stats["min_observed"] == 60.0
        assert stats["max_observed"] == 63.0


class TestPositionAdjuster:
    """Test suite for PositionAdjuster."""

    @pytest.fixture
    def mock_strategy(self):
        """Create a mock trading strategy."""
        strategy = Mock()
        strategy.client = Mock()
        strategy.positions = []
        return strategy

    @pytest.fixture
    def sample_market(self):
        """Create a sample market."""
        outcomes = [
            PolymarketOutcome(
                token_id="token_60_61",
                price=0.20,
                temperature_range=TemperatureRange.from_label("60-61°F")
            ),
            PolymarketOutcome(
                token_id="token_62_63",
                price=0.30,
                temperature_range=TemperatureRange.from_label("62-63°F")
            ),
            PolymarketOutcome(
                token_id="token_64_65",
                price=0.35,
                temperature_range=TemperatureRange.from_label("64-65°F")
            ),
        ]

        return TemperatureMarket(
            market_id="market_test",
            question="Temp test?",
            target_date=datetime.now(),
            outcomes=outcomes
        )

    @pytest.fixture
    def adjuster(self, mock_strategy, sample_market):
        """Create a PositionAdjuster instance."""
        return PositionAdjuster(
            strategy=mock_strategy,
            market=sample_market
        )

    def test_initialization(self, adjuster, sample_market):
        """Test adjuster initialization."""
        assert adjuster.market == sample_market

    def test_adjust_for_temperature_same_range(self, adjuster, mock_strategy):
        """Test adjustment when temperature stays in same range."""
        # Old: 62°F, New: 63°F -> both in 62-63°F range
        adjusted = adjuster.adjust_for_temperature(62.0, 63.0)

        # No adjustment needed
        assert adjusted == False

    def test_adjust_for_temperature_different_range(self, adjuster, mock_strategy, sample_market):
        """Test adjustment when temperature moves to different range."""
        # Setup: have position on 60-61°F
        old_position = Position(
            market_id=sample_market.market_id,
            outcome_id="token_60_61",
            shares=100.0,
            avg_entry_price=0.20,
            current_price=0.22
        )

        mock_strategy.get_position_for_market.return_value = old_position
        mock_strategy.client.close_position.return_value = True
        mock_strategy.execute_order.return_value = True

        # Temperature changes from 61°F to 63°F (different ranges)
        adjusted = adjuster.adjust_for_temperature(61.0, 63.0)

        # Should adjust
        assert adjusted == True
        mock_strategy.client.close_position.assert_called_once()
        mock_strategy.execute_order.assert_called_once()

    def test_adjust_for_temperature_no_position(self, adjuster, mock_strategy):
        """Test adjustment when no position exists."""
        mock_strategy.get_position_for_market.return_value = None
        mock_strategy.execute_order.return_value = True

        # Temperature changes but we have no position
        adjusted = adjuster.adjust_for_temperature(61.0, 63.0)

        # Should still try to open new position
        assert adjusted == True
        mock_strategy.execute_order.assert_called_once()
