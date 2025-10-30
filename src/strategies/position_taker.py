"""
Position taking strategy for temperature markets.
Analyzes forecasts and takes directional positions.
"""

from typing import Optional, Dict, Tuple
from datetime import datetime

from .base import BaseStrategy
from ..models.market import TemperatureMarket, PolymarketOutcome, WeatherForecast
from ..models.trade import Order, Position, OrderSide, OrderType
from ..utils.logger import get_logger, log_market_analysis
from ..utils.helpers import get_confidence_score, calculate_kelly_criterion

logger = get_logger()


class PositionTakerStrategy(BaseStrategy):
    """
    Strategy that takes directional positions based on weather forecasts.

    Key features:
    - Analyzes forecast vs market prices to find edge
    - Uses Kelly Criterion for position sizing
    - Adjusts positions when forecasts change
    - Scales position size based on confidence (days ahead)
    """

    def __init__(
        self,
        client,
        max_position_size: float = 100.0,
        max_exposure_per_market: float = 200.0,
        min_edge: float = 0.05,  # 5% minimum edge
        kelly_fraction: float = 0.25,  # Conservative Kelly
        advance_days: int = 3  # Start trading J-3
    ):
        """
        Initialize position taking strategy.

        Args:
            client: Polymarket client or simulator
            max_position_size: Max size per single position (USDC)
            max_exposure_per_market: Max total exposure per market (USDC)
            min_edge: Minimum edge required to trade
            kelly_fraction: Fraction of Kelly to use (0.25 = 25% Kelly)
            advance_days: How many days in advance to start trading
        """
        super().__init__(client, name="PositionTaker")

        self.max_position_size = max_position_size
        self.max_exposure_per_market = max_exposure_per_market
        self.min_edge = min_edge
        self.kelly_fraction = kelly_fraction
        self.advance_days = advance_days

        logger.info(
            f"PositionTaker initialized | "
            f"Max position: {max_position_size} USDC | "
            f"Min edge: {min_edge * 100}% | "
            f"Kelly fraction: {kelly_fraction}"
        )

    def analyze_market(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> Optional[Order]:
        """
        Analyze market and decide if we should take a position.

        Args:
            market: Temperature market
            forecast: Weather forecast

        Returns:
            Order to execute, or None
        """
        # Check if market is within our trading window
        days_until = market.days_until_target()

        if days_until > self.advance_days or days_until < 0:
            logger.debug(
                f"Market outside trading window: {days_until} days "
                f"(advance_days={self.advance_days})"
            )
            return None

        # Find the best outcome based on forecast
        predicted_temp = forecast.max_temperature
        result = self._find_best_outcome(market, predicted_temp, forecast.confidence)

        if result is None:
            logger.debug(f"No suitable outcome found for {predicted_temp}°F")
            return None

        outcome, edge = result

        # Check if edge is sufficient
        if edge < self.min_edge:
            logger.debug(
                f"Edge too low: {edge:.2%} < {self.min_edge:.2%}"
            )
            return None

        # Check current exposure on this market
        current_exposure = self._get_market_exposure(market.market_id)

        if current_exposure >= self.max_exposure_per_market:
            logger.warning(
                f"Max exposure reached for market {market.market_id[:8]}...: "
                f"{current_exposure:.2f} >= {self.max_exposure_per_market:.2f}"
            )
            return None

        # Calculate position size
        position_size = self._calculate_position_size(
            edge=edge,
            confidence=forecast.confidence,
            days_ahead=days_until,
            current_exposure=current_exposure
        )

        if position_size == 0:
            logger.debug("Position size calculated to 0")
            return None

        # Log analysis
        log_market_analysis(
            market_id=market.market_id,
            predicted_temp=predicted_temp,
            selected_outcome=outcome.temperature_range.label,
            confidence=forecast.confidence,
            edge=edge,
            position_size=position_size
        )

        # Create order
        order = Order(
            market_id=market.market_id,
            outcome_id=outcome.token_id,
            side=OrderSide.BUY,
            size=position_size,
            price=outcome.price,
            order_type=OrderType.LIMIT
        )

        return order

    def _find_best_outcome(
        self,
        market: TemperatureMarket,
        predicted_temp: float,
        confidence: float
    ) -> Optional[Tuple[PolymarketOutcome, float]]:
        """
        Find the outcome with best edge for predicted temperature.

        Args:
            market: Temperature market
            predicted_temp: Predicted temperature
            confidence: Forecast confidence

        Returns:
            Tuple of (outcome, edge) or None
        """
        # Find outcome that contains predicted temperature
        matching_outcome = market.get_outcome_by_temperature(predicted_temp)

        if matching_outcome is None:
            return None

        # Calculate edge
        # Our probability = confidence (we're confident this is the right outcome)
        # Market probability = current price
        # Edge = our_prob - market_prob
        edge = confidence - matching_outcome.price

        return (matching_outcome, edge)

    def _calculate_position_size(
        self,
        edge: float,
        confidence: float,
        days_ahead: int,
        current_exposure: float
    ) -> float:
        """
        Calculate position size using Kelly Criterion.

        Args:
            edge: Calculated edge
            confidence: Forecast confidence
            days_ahead: Days until target date
            current_exposure: Current exposure on this market

        Returns:
            Position size in USDC
        """
        # Get available balance
        balance = self.client.get_balance()

        # Use Kelly Criterion
        # Edge = expected value - 1
        # For binary outcomes: kelly = edge / (odds - 1)
        # We use fractional Kelly for conservative sizing

        # Calculate decimal odds from edge
        # If edge = 0.3 and market price = 0.4, implied odds = 1/0.4 = 2.5
        # But we think true prob = 0.7, so our odds = 1/0.7 = 1.43

        # Simplified: use confidence as our probability
        if confidence <= 0 or confidence >= 1:
            return 0.0

        our_prob = confidence
        implied_odds = 1.0 / our_prob if our_prob > 0 else 1.0

        kelly_fraction_result = calculate_kelly_criterion(
            edge=edge,
            odds=implied_odds,
            fraction=self.kelly_fraction
        )

        # Calculate size from Kelly fraction
        kelly_size = balance * kelly_fraction_result

        # Apply limits
        # 1. Max position size
        size = min(kelly_size, self.max_position_size)

        # 2. Max exposure per market
        remaining_exposure = self.max_exposure_per_market - current_exposure
        size = min(size, remaining_exposure)

        # 3. Scale by days ahead (less aggressive when far out)
        # J-0: 100%, J-1: 90%, J-2: 80%, J-3: 70%
        days_scaling = max(0.5, 1.0 - (days_ahead * 0.1))
        size = size * days_scaling

        # Round to 2 decimal places
        size = round(size, 2)

        return max(0, size)

    def _get_market_exposure(self, market_id: str) -> float:
        """
        Get current exposure on a specific market.

        Args:
            market_id: Market identifier

        Returns:
            Total exposure in USDC
        """
        exposure = 0.0

        for position in self.positions:
            if position.market_id == market_id:
                exposure += position.current_value()

        return exposure

    def should_adjust_position(
        self,
        position: Position,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> Optional[Order]:
        """
        Determine if we should adjust an existing position.

        Args:
            position: Current position
            market: Market information
            forecast: Updated forecast

        Returns:
            Order to adjust, or None
        """
        # Find the outcome we're currently holding
        current_outcome = market.get_outcome_by_token_id(position.outcome_id)

        if current_outcome is None:
            logger.warning(f"Could not find outcome {position.outcome_id[:8]}...")
            return None

        # Check if forecast still supports this outcome
        predicted_temp = forecast.max_temperature

        if current_outcome.temperature_range.contains(predicted_temp):
            # Forecast still supports our position, no adjustment needed
            logger.debug(
                f"Forecast ({predicted_temp}°F) still supports position "
                f"{current_outcome.temperature_range.label}"
            )
            return None

        # Forecast has changed significantly, close this position
        logger.info(
            f"Forecast changed to {predicted_temp}°F, "
            f"closing position on {current_outcome.temperature_range.label}"
        )

        # Create sell order
        order = Order(
            market_id=position.market_id,
            outcome_id=position.outcome_id,
            side=OrderSide.SELL,
            size=position.shares * position.current_price,  # Size in USDC
            price=position.current_price,
            order_type=OrderType.MARKET  # Use market order for quick exit
        )

        return order

    def rebalance_positions(
        self,
        markets: Dict[str, TemperatureMarket],
        forecasts: Dict[str, WeatherForecast]
    ) -> int:
        """
        Rebalance all positions based on updated forecasts.

        Args:
            markets: Dict of market_id -> TemperatureMarket
            forecasts: Dict of market_id -> WeatherForecast

        Returns:
            Number of positions adjusted
        """
        adjusted = 0

        for position in self.positions:
            market = markets.get(position.market_id)
            forecast = forecasts.get(position.market_id)

            if market is None or forecast is None:
                logger.warning(
                    f"Missing market or forecast for position "
                    f"{position.outcome_id[:8]}..."
                )
                continue

            # Check if we should adjust
            adjustment_order = self.should_adjust_position(position, market, forecast)

            if adjustment_order:
                if self.execute_order(adjustment_order):
                    adjusted += 1

        logger.info(f"[{self.name}] Rebalanced {adjusted} positions")
        return adjusted

    def get_strategy_stats(self) -> Dict:
        """
        Get strategy statistics.

        Returns:
            Dictionary with strategy stats
        """
        total_exposure = self.get_total_exposure()
        total_pnl = self.get_total_pnl()

        return {
            "strategy": self.name,
            "num_positions": len(self.positions),
            "total_exposure": total_exposure,
            "total_pnl": total_pnl,
            "max_position_size": self.max_position_size,
            "max_exposure_per_market": self.max_exposure_per_market,
            "min_edge": self.min_edge,
            "active_orders": len(self.active_orders)
        }
