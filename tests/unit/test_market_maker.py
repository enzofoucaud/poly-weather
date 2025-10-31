"""
Tests for Market Making Strategy.
"""

import pytest
from datetime import datetime, timedelta

from src.strategies.market_maker import MarketMakerStrategy
from src.clients.polymarket_simulator import PolymarketSimulator
from src.models.market import (
    TemperatureMarket,
    PolymarketOutcome,
    TemperatureRange,
    WeatherForecast
)
from src.models.trade import Position


class TestMarketMakerStrategy:
    """Test suite for MarketMakerStrategy."""

    @pytest.fixture
    def simulator(self):
        """Create a Polymarket simulator."""
        return PolymarketSimulator(initial_balance=1000.0)

    @pytest.fixture
    def strategy(self, simulator):
        """Create a MarketMakerStrategy instance."""
        return MarketMakerStrategy(
            client=simulator,
            min_spread=0.02,
            base_size=50.0,
            max_inventory=500.0,
            inventory_skew_threshold=0.7,
            update_interval=30,
            max_daily_loss=50.0
        )

    @pytest.fixture
    def sample_outcome(self):
        """Create a sample outcome."""
        return PolymarketOutcome(
            token_id="token_62_63",
            price=0.30,
            temperature_range=TemperatureRange.from_label("62-63°F")
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
        assert strategy.name == "MarketMaker"
        assert strategy.min_spread == 0.02
        assert strategy.base_size == 50.0
        assert strategy.max_inventory == 500.0
        assert strategy.stopped == False

    def test_calculate_fair_value_matching_forecast(self, strategy, sample_outcome, sample_forecast):
        """Test fair value calculation when forecast matches outcome."""
        # Forecast predicts 63°F, outcome is 62-63°F
        fair_value = strategy.calculate_fair_value(sample_outcome, sample_forecast)

        # Should use confidence as fair value
        assert fair_value == pytest.approx(0.85, abs=0.01)

    def test_calculate_fair_value_non_matching_forecast(self, strategy, sample_outcome):
        """Test fair value calculation when forecast doesn't match outcome."""
        # Forecast predicts 70°F, outcome is 62-63°F
        forecast = WeatherForecast(
            date=datetime.now() + timedelta(days=1),
            max_temperature=70.0,
            confidence=0.85,
            source="test"
        )

        fair_value = strategy.calculate_fair_value(sample_outcome, forecast)

        # Should be lower than market price
        assert fair_value < sample_outcome.price

    def test_calculate_quotes_no_inventory(self, strategy):
        """Test quote calculation with no inventory."""
        fair_value = 0.50
        spread = 0.04

        bid, ask = strategy.calculate_quotes(
            fair_value=fair_value,
            spread=spread,
            inventory_level=0.0
        )

        # Should be symmetric around fair value
        assert bid == pytest.approx(0.48, abs=0.01)  # 0.50 - 0.02
        assert ask == pytest.approx(0.52, abs=0.01)  # 0.50 + 0.02
        assert ask > bid

    def test_calculate_quotes_with_long_inventory(self, strategy):
        """Test quote calculation with long inventory (want to sell)."""
        fair_value = 0.50
        spread = 0.04
        inventory_level = 0.8  # 80% long

        bid, ask = strategy.calculate_quotes(
            fair_value=fair_value,
            spread=spread,
            inventory_level=inventory_level
        )

        # Both bid and ask should be lower to encourage selling
        assert bid < 0.48
        assert ask < 0.52
        assert ask > bid

    def test_calculate_quotes_with_short_inventory(self, strategy):
        """Test quote calculation with short inventory (want to buy)."""
        fair_value = 0.50
        spread = 0.04
        inventory_level = -0.8  # 80% short

        bid, ask = strategy.calculate_quotes(
            fair_value=fair_value,
            spread=spread,
            inventory_level=inventory_level
        )

        # Both bid and ask should be higher to encourage buying
        assert bid > 0.48
        assert ask > 0.52
        assert ask > bid

    def test_get_inventory_level_neutral(self, strategy):
        """Test inventory level calculation with no position."""
        level = strategy.get_inventory_level("outcome_123")

        assert level == 0.0

    def test_get_inventory_level_long(self, strategy):
        """Test inventory level calculation with long position."""
        strategy.inventory["outcome_123"] = 250.0  # 50% of max_inventory

        level = strategy.get_inventory_level("outcome_123")

        assert level == pytest.approx(0.5, abs=0.01)

    def test_get_inventory_level_max_long(self, strategy):
        """Test inventory level at maximum."""
        strategy.inventory["outcome_123"] = 500.0  # 100% of max_inventory

        level = strategy.get_inventory_level("outcome_123")

        assert level == pytest.approx(1.0, abs=0.01)

    def test_should_skew_quotes_below_threshold(self, strategy):
        """Test skew detection below threshold."""
        strategy.inventory["outcome_123"] = 300.0  # 60% of max

        should_skew = strategy.should_skew_quotes("outcome_123")

        # 60% < 70% threshold
        assert should_skew == False

    def test_should_skew_quotes_above_threshold(self, strategy):
        """Test skew detection above threshold."""
        strategy.inventory["outcome_123"] = 400.0  # 80% of max

        should_skew = strategy.should_skew_quotes("outcome_123")

        # 80% >= 70% threshold
        assert should_skew == True

    def test_update_inventory(self, strategy):
        """Test inventory update from positions."""
        # Add some positions
        strategy.positions = [
            Position(
                market_id="market_1",
                outcome_id="outcome_a",
                shares=100.0,
                avg_entry_price=0.50,
                current_price=0.55
            ),
            Position(
                market_id="market_1",
                outcome_id="outcome_b",
                shares=200.0,
                avg_entry_price=0.30,
                current_price=0.35
            ),
        ]

        strategy.update_inventory()

        assert strategy.inventory["outcome_a"] == 100.0
        assert strategy.inventory["outcome_b"] == 200.0
        assert len(strategy.inventory) == 2

    def test_check_circuit_breakers_normal(self, strategy, simulator):
        """Test circuit breakers under normal conditions."""
        # Set session start balance
        strategy.session_start_balance = simulator.get_balance()

        should_stop = strategy.check_circuit_breakers()

        assert should_stop == False
        assert strategy.stopped == False

    def test_check_circuit_breakers_max_loss(self, strategy, simulator):
        """Test circuit breaker triggers on max loss."""
        # Set session start balance higher
        strategy.session_start_balance = 1100.0  # Started with 1100, now have 1000
        # This creates a loss of -100, which exceeds max_daily_loss of 50

        should_stop = strategy.check_circuit_breakers()

        assert should_stop == True
        assert strategy.stopped == True

    def test_place_market_making_orders(self, strategy, sample_outcome, simulator):
        """Test placing bid and ask orders."""
        bid_id, ask_id = strategy.place_market_making_orders(
            outcome=sample_outcome,
            bid_price=0.48,
            ask_price=0.52,
            size=50.0
        )

        # Both orders should be placed
        assert bid_id is not None
        assert ask_id is not None
        assert bid_id != ask_id

    def test_cancel_all_orders(self, strategy, simulator, sample_outcome):
        """Test canceling all active orders."""
        # Place some orders
        bid_id, ask_id = strategy.place_market_making_orders(
            outcome=sample_outcome,
            bid_price=0.48,
            ask_price=0.52,
            size=50.0
        )

        # Track them
        strategy.active_orders[bid_id] = None
        strategy.active_orders[ask_id] = None

        # Cancel all
        cancelled = strategy.cancel_all_orders()

        assert cancelled == 2
        assert len(strategy.active_orders) == 0

    def test_get_strategy_stats(self, strategy):
        """Test strategy statistics retrieval."""
        strategy.inventory = {"outcome_a": 100.0, "outcome_b": 200.0}
        strategy.daily_pnl = 15.50

        stats = strategy.get_strategy_stats()

        assert stats["strategy"] == "MarketMaker"
        assert stats["num_outcomes_with_inventory"] == 2
        assert stats["total_inventory"] == 300.0
        assert stats["daily_pnl"] == 15.50
        assert stats["stopped"] == False
