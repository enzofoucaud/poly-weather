"""
Tests for Position Taking Strategy.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from src.strategies.position_taker import PositionTakerStrategy
from src.clients.polymarket_simulator import PolymarketSimulator
from src.models.market import (
    TemperatureMarket,
    PolymarketOutcome,
    TemperatureRange,
    WeatherForecast
)
from src.models.trade import Position, OrderSide


class TestPositionTakerStrategy:
    """Test suite for PositionTakerStrategy."""

    @pytest.fixture
    def simulator(self):
        """Create a Polymarket simulator."""
        return PolymarketSimulator(initial_balance=1000.0)

    @pytest.fixture
    def strategy(self, simulator):
        """Create a PositionTakerStrategy instance."""
        return PositionTakerStrategy(
            client=simulator,
            max_position_size=100.0,
            max_exposure_per_market=200.0,
            min_edge=0.05,
            kelly_fraction=0.25,
            advance_days=3
        )

    @pytest.fixture
    def sample_market(self):
        """Create a sample temperature market."""
        tomorrow = datetime.now() + timedelta(days=1)

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
            PolymarketOutcome(
                token_id="token_66_plus",
                price=0.15,
                temperature_range=TemperatureRange.from_label("66°F or higher")
            ),
        ]

        return TemperatureMarket(
            market_id="market_test_123",
            question="Highest temperature in NYC tomorrow?",
            target_date=tomorrow,
            outcomes=outcomes
        )

    @pytest.fixture
    def sample_forecast(self):
        """Create a sample weather forecast."""
        tomorrow = datetime.now() + timedelta(days=1)

        return WeatherForecast(
            date=tomorrow,
            max_temperature=63.0,
            confidence=0.85,
            source="test"
        )

    def test_initialization(self, strategy):
        """Test strategy initialization."""
        assert strategy.name == "PositionTaker"
        assert strategy.max_position_size == 100.0
        assert strategy.min_edge == 0.05
        assert strategy.kelly_fraction == 0.25

    def test_find_best_outcome(self, strategy, sample_market):
        """Test finding the best outcome for a predicted temperature."""
        # Predict 63°F -> should select "62-63°F" outcome
        result = strategy._find_best_outcome(
            market=sample_market,
            predicted_temp=63.0,
            confidence=0.85
        )

        assert result is not None
        outcome, edge = result

        # Should select the 62-63 range
        assert outcome.temperature_range.contains(63.0)
        assert outcome.token_id == "token_62_63"

        # Edge = confidence - market_price = 0.85 - 0.30 = 0.55
        assert edge == pytest.approx(0.55, abs=0.01)

    def test_find_best_outcome_no_match(self, strategy, sample_market):
        """Test when no outcome matches predicted temperature."""
        # Predict 70°F -> no exact match
        result = strategy._find_best_outcome(
            market=sample_market,
            predicted_temp=70.0,
            confidence=0.85
        )

        # Should match "66°F or higher"
        assert result is not None
        outcome, edge = result
        assert outcome.token_id == "token_66_plus"

    def test_calculate_position_size(self, strategy):
        """Test position size calculation."""
        size = strategy._calculate_position_size(
            edge=0.30,
            confidence=0.85,
            days_ahead=1,
            current_exposure=0.0
        )

        # Should return a positive size
        assert size > 0

        # Should not exceed max position size
        assert size <= strategy.max_position_size

    def test_calculate_position_size_with_existing_exposure(self, strategy):
        """Test position sizing respects existing exposure limits."""
        # Already have 150 USDC exposure (out of 200 max)
        size = strategy._calculate_position_size(
            edge=0.30,
            confidence=0.85,
            days_ahead=1,
            current_exposure=150.0
        )

        # Should not exceed remaining exposure (200 - 150 = 50)
        assert size <= 50.0

    def test_calculate_position_size_scales_with_days(self, strategy):
        """Test that position size scales with days ahead."""
        # J-0 (tomorrow)
        size_j0 = strategy._calculate_position_size(
            edge=0.30,
            confidence=0.85,
            days_ahead=0,
            current_exposure=0.0
        )

        # J-3
        size_j3 = strategy._calculate_position_size(
            edge=0.30,
            confidence=0.85,
            days_ahead=3,
            current_exposure=0.0
        )

        # J-0 should have larger position than J-3
        assert size_j0 > size_j3

    def test_analyze_market_with_good_edge(self, strategy, sample_market, sample_forecast):
        """Test market analysis with sufficient edge."""
        order = strategy.analyze_market(sample_market, sample_forecast)

        assert order is not None
        assert order.side == OrderSide.BUY
        assert order.outcome_id == "token_62_63"  # Should select 62-63 for 63°F prediction
        assert order.size > 0

    def test_analyze_market_insufficient_edge(self, strategy, sample_market):
        """Test that orders are not placed when edge is insufficient."""
        # Create forecast with low confidence -> low edge
        forecast = WeatherForecast(
            date=sample_market.target_date,
            max_temperature=63.0,
            confidence=0.32,  # Only 0.32 - 0.30 = 0.02 edge (< min_edge of 0.05)
            source="test"
        )

        order = strategy.analyze_market(sample_market, forecast)

        # Should not place order due to insufficient edge
        assert order is None

    def test_analyze_market_outside_window(self, strategy, sample_forecast):
        """Test that markets outside trading window are skipped."""
        # Create market 10 days in future (beyond advance_days=3)
        far_future = datetime.now() + timedelta(days=10)

        market = TemperatureMarket(
            market_id="market_far",
            question="Temp in 10 days?",
            target_date=far_future,
            outcomes=[
                PolymarketOutcome(
                    token_id="token_test",
                    price=0.30,
                    temperature_range=TemperatureRange.from_label("62-63°F")
                )
            ]
        )

        order = strategy.analyze_market(market, sample_forecast)

        # Should not place order (outside window)
        assert order is None

    def test_should_adjust_position_forecast_matches(self, strategy, sample_market, sample_forecast):
        """Test position adjustment when forecast still supports position."""
        # Position on 62-63°F
        position = Position(
            market_id=sample_market.market_id,
            outcome_id="token_62_63",
            shares=100.0,
            avg_entry_price=0.30,
            current_price=0.32
        )

        # Forecast predicts 63°F (still in range)
        order = strategy.should_adjust_position(position, sample_market, sample_forecast)

        # No adjustment needed
        assert order is None

    def test_should_adjust_position_forecast_changed(self, strategy, sample_market):
        """Test position adjustment when forecast changes significantly."""
        # Position on 62-63°F
        position = Position(
            market_id=sample_market.market_id,
            outcome_id="token_62_63",
            shares=100.0,
            avg_entry_price=0.30,
            current_price=0.32
        )

        # Forecast now predicts 67°F (outside range)
        changed_forecast = WeatherForecast(
            date=sample_market.target_date,
            max_temperature=67.0,
            confidence=0.85,
            source="test"
        )

        order = strategy.should_adjust_position(position, sample_market, changed_forecast)

        # Should create sell order
        assert order is not None
        assert order.side == OrderSide.SELL
        assert order.outcome_id == "token_62_63"

    def test_get_market_exposure(self, strategy):
        """Test calculation of market exposure."""
        # Add some positions
        strategy.positions = [
            Position(
                market_id="market_1",
                outcome_id="outcome_a",
                shares=100,
                avg_entry_price=0.50,
                current_price=0.55
            ),
            Position(
                market_id="market_1",
                outcome_id="outcome_b",
                shares=50,
                avg_entry_price=0.30,
                current_price=0.35
            ),
            Position(
                market_id="market_2",
                outcome_id="outcome_c",
                shares=75,
                avg_entry_price=0.40,
                current_price=0.45
            ),
        ]

        # Exposure on market_1 = (100 * 0.55) + (50 * 0.35) = 55 + 17.5 = 72.5
        exposure = strategy._get_market_exposure("market_1")
        assert exposure == pytest.approx(72.5, abs=0.1)

        # Exposure on market_2 = 75 * 0.45 = 33.75
        exposure = strategy._get_market_exposure("market_2")
        assert exposure == pytest.approx(33.75, abs=0.1)

    def test_get_strategy_stats(self, strategy):
        """Test strategy statistics retrieval."""
        stats = strategy.get_strategy_stats()

        assert stats["strategy"] == "PositionTaker"
        assert stats["num_positions"] == 0
        assert stats["max_position_size"] == 100.0
        assert stats["min_edge"] == 0.05
