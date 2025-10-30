"""
Market making strategy for temperature markets.
Places simultaneous bid and ask orders to capture the spread.
"""

from typing import Optional, Dict, Tuple, List
from datetime import datetime
import time

from .base import BaseStrategy
from ..models.market import TemperatureMarket, PolymarketOutcome, WeatherForecast
from ..models.trade import Order, Position, OrderSide, OrderType, OrderStatus
from ..utils.logger import get_logger, log_risk_alert
from ..utils.helpers import round_to_nearest

logger = get_logger()


class MarketMakerStrategy(BaseStrategy):
    """
    Market making strategy that provides liquidity by placing bid/ask pairs.

    Key features:
    - Calculates fair value based on weather forecasts
    - Places symmetric bid/ask orders around fair value
    - Manages inventory to stay market neutral
    - Adjusts quotes based on inventory levels
    - Implements circuit breakers for risk management
    """

    def __init__(
        self,
        client,
        min_spread: float = 0.02,  # 2% minimum spread
        base_size: float = 50.0,  # Base order size in USDC
        max_inventory: float = 500.0,  # Max shares per outcome
        inventory_skew_threshold: float = 0.7,  # 70% of max
        update_interval: int = 30,  # Seconds between quote updates
        max_daily_loss: float = 50.0,  # Circuit breaker
    ):
        """
        Initialize market making strategy.

        Args:
            client: Polymarket client or simulator
            min_spread: Minimum bid-ask spread (0.02 = 2%)
            base_size: Base order size in USDC
            max_inventory: Maximum inventory per outcome
            inventory_skew_threshold: Threshold to start skewing quotes (0-1)
            update_interval: Seconds between quote updates
            max_daily_loss: Maximum daily loss before stopping
        """
        super().__init__(client, name="MarketMaker")

        self.min_spread = min_spread
        self.base_size = base_size
        self.max_inventory = max_inventory
        self.inventory_skew_threshold = inventory_skew_threshold
        self.update_interval = update_interval
        self.max_daily_loss = max_daily_loss

        # Track inventory per outcome
        self.inventory: Dict[str, float] = {}  # outcome_id -> shares

        # Track P&L
        self.session_start_balance = client.get_balance()
        self.daily_pnl = 0.0
        self.stopped = False

        logger.info(
            f"MarketMaker initialized | "
            f"Min spread: {min_spread * 100}% | "
            f"Base size: {base_size} USDC | "
            f"Max inventory: {max_inventory} shares"
        )

    def calculate_fair_value(
        self,
        outcome: PolymarketOutcome,
        forecast: WeatherForecast
    ) -> float:
        """
        Calculate fair value for an outcome based on forecast.

        Args:
            outcome: Market outcome
            forecast: Weather forecast

        Returns:
            Fair value price (0-1)
        """
        predicted_temp = forecast.max_temperature
        confidence = forecast.confidence

        # Check if forecast predicts this outcome
        if outcome.temperature_range.contains(predicted_temp):
            # Our forecast supports this outcome
            # Fair value = confidence (our probability it happens)
            fair_value = confidence
        else:
            # Our forecast doesn't support this outcome
            # Fair value = 1 - confidence (probability it doesn't happen)
            # But we need to distribute among other outcomes
            # Simplified: use current market price with slight adjustment
            fair_value = outcome.price * (1.0 - confidence * 0.5)

        # Clamp between reasonable bounds
        fair_value = max(0.01, min(0.99, fair_value))

        return fair_value

    def calculate_quotes(
        self,
        fair_value: float,
        spread: float,
        inventory_level: float = 0.0
    ) -> Tuple[float, float]:
        """
        Calculate bid and ask prices.

        Args:
            fair_value: Calculated fair value
            spread: Desired spread
            inventory_level: Current inventory level (-1 to 1, where 0 is neutral)

        Returns:
            Tuple of (bid_price, ask_price)
        """
        # Base quotes symmetric around fair value
        half_spread = spread / 2
        base_bid = fair_value - half_spread
        base_ask = fair_value + half_spread

        # Adjust for inventory
        # If inventory_level > 0 (long): lower both bid and ask to encourage selling
        # If inventory_level < 0 (short): raise both bid and ask to encourage buying
        inventory_adjustment = inventory_level * half_spread

        bid = base_bid - inventory_adjustment
        ask = base_ask - inventory_adjustment

        # Ensure bid < ask
        if bid >= ask:
            # Force minimum spread
            mid = (bid + ask) / 2
            bid = mid - (self.min_spread / 2)
            ask = mid + (self.min_spread / 2)

        # Clamp to valid price range
        bid = max(0.01, min(0.98, bid))
        ask = max(0.02, min(0.99, ask))

        # Ensure bid < ask after clamping
        if bid >= ask:
            ask = bid + self.min_spread

        # Round to reasonable precision
        bid = round_to_nearest(bid, 0.01)
        ask = round_to_nearest(ask, 0.01)

        return (bid, ask)

    def get_inventory_level(self, outcome_id: str) -> float:
        """
        Get normalized inventory level for an outcome.

        Args:
            outcome_id: Outcome identifier

        Returns:
            Inventory level from -1 (max short) to 1 (max long), 0 is neutral
        """
        current_inventory = self.inventory.get(outcome_id, 0.0)

        if self.max_inventory == 0:
            return 0.0

        # Normalize: 0 shares = 0, max_inventory shares = 1
        normalized = current_inventory / self.max_inventory

        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, normalized))

    def should_skew_quotes(self, outcome_id: str) -> bool:
        """
        Check if inventory is high enough to skew quotes.

        Args:
            outcome_id: Outcome identifier

        Returns:
            True if should skew quotes
        """
        inventory_level = abs(self.get_inventory_level(outcome_id))
        return inventory_level >= self.inventory_skew_threshold

    def place_market_making_orders(
        self,
        outcome: PolymarketOutcome,
        bid_price: float,
        ask_price: float,
        size: float
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Place both bid and ask orders.

        Args:
            outcome: Outcome to make market on
            bid_price: Bid price
            ask_price: Ask price
            size: Order size in USDC

        Returns:
            Tuple of (bid_order_id, ask_order_id)
        """
        bid_order_id = None
        ask_order_id = None

        try:
            # Place bid (buy) order
            bid_order = Order(
                market_id="",  # Will be set when we have market context
                outcome_id=outcome.token_id,
                side=OrderSide.BUY,
                size=size,
                price=bid_price,
                order_type=OrderType.LIMIT
            )

            bid_order_id = self.client.place_order(bid_order)
            logger.info(
                f"[{self.name}] Bid placed: {size:.2f} @ {bid_price:.4f} "
                f"| ID: {bid_order_id[:8]}..."
            )

        except Exception as e:
            logger.error(f"[{self.name}] Failed to place bid: {e}")

        try:
            # Place ask (sell) order
            ask_order = Order(
                market_id="",
                outcome_id=outcome.token_id,
                side=OrderSide.SELL,
                size=size,
                price=ask_price,
                order_type=OrderType.LIMIT
            )

            ask_order_id = self.client.place_order(ask_order)
            logger.info(
                f"[{self.name}] Ask placed: {size:.2f} @ {ask_price:.4f} "
                f"| ID: {ask_order_id[:8]}..."
            )

        except Exception as e:
            logger.error(f"[{self.name}] Failed to place ask: {e}")

        return (bid_order_id, ask_order_id)

    def cancel_all_orders(self) -> int:
        """
        Cancel all active orders.

        Returns:
            Number of orders cancelled
        """
        cancelled = 0

        for order_id in list(self.active_orders.keys()):
            try:
                if self.client.cancel_order(order_id):
                    cancelled += 1
                    del self.active_orders[order_id]
            except Exception as e:
                logger.error(f"[{self.name}] Failed to cancel order {order_id}: {e}")

        logger.info(f"[{self.name}] Cancelled {cancelled} orders")
        return cancelled

    def update_inventory(self) -> None:
        """Update inventory from current positions."""
        self.inventory.clear()

        for position in self.positions:
            self.inventory[position.outcome_id] = position.shares

        logger.debug(
            f"[{self.name}] Inventory updated: "
            f"{len(self.inventory)} outcomes with positions"
        )

    def check_circuit_breakers(self) -> bool:
        """
        Check if circuit breakers should stop market making.

        Returns:
            True if should stop
        """
        # Calculate current P&L
        current_balance = self.client.get_balance()
        position_value = sum(p.current_value() for p in self.positions)
        total_value = current_balance + position_value

        self.daily_pnl = total_value - self.session_start_balance

        # Check daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            log_risk_alert(
                alert_type="DAILY_LOSS",
                message="Daily loss limit exceeded",
                current_value=abs(self.daily_pnl),
                limit=self.max_daily_loss,
                action="STOPPED"
            )
            self.stopped = True
            return True

        # Check inventory limits
        for outcome_id, shares in self.inventory.items():
            if shares > self.max_inventory:
                log_risk_alert(
                    alert_type="INVENTORY",
                    message=f"Inventory limit exceeded for {outcome_id[:8]}...",
                    current_value=shares,
                    limit=self.max_inventory,
                    action="PAUSED"
                )
                # Don't stop, but should reduce exposure
                return False

        return False

    def run_market_making_loop(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast,
        duration: Optional[int] = None
    ) -> None:
        """
        Run market making loop for a market.

        Args:
            market: Temperature market
            forecast: Weather forecast
            duration: Duration to run in seconds (None = indefinite)
        """
        logger.info(
            f"[{self.name}] Starting market making loop for "
            f"{market.question}"
        )

        start_time = time.time()

        while not self.stopped:
            try:
                # Check circuit breakers
                if self.check_circuit_breakers():
                    logger.warning(f"[{self.name}] Circuit breaker triggered, stopping")
                    break

                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    logger.info(f"[{self.name}] Duration reached, stopping")
                    break

                # Update positions and inventory
                self.update_positions()
                self.update_inventory()

                # Cancel old orders
                self.cancel_all_orders()

                # Place new orders for each outcome
                for outcome in market.outcomes:
                    # Calculate fair value
                    fair_value = self.calculate_fair_value(outcome, forecast)

                    # Get inventory level
                    inventory_level = self.get_inventory_level(outcome.token_id)

                    # Determine spread (wider if inventory is high)
                    spread = self.min_spread
                    if self.should_skew_quotes(outcome.token_id):
                        spread *= 1.5  # Widen spread when inventory is high

                    # Calculate quotes
                    bid, ask = self.calculate_quotes(
                        fair_value=fair_value,
                        spread=spread,
                        inventory_level=inventory_level
                    )

                    # Determine size (reduce if inventory is high)
                    size = self.base_size
                    if abs(inventory_level) > 0.5:
                        size *= (1.0 - abs(inventory_level))

                    # Place orders
                    self.place_market_making_orders(
                        outcome=outcome,
                        bid_price=bid,
                        ask_price=ask,
                        size=size
                    )

                # Wait before next update
                logger.debug(
                    f"[{self.name}] Sleeping for {self.update_interval}s"
                )
                time.sleep(self.update_interval)

            except KeyboardInterrupt:
                logger.info(f"[{self.name}] Interrupted by user")
                break

            except Exception as e:
                logger.error(f"[{self.name}] Error in market making loop: {e}")
                time.sleep(self.update_interval)

        # Cleanup
        logger.info(f"[{self.name}] Stopping market making, cancelling all orders")
        self.cancel_all_orders()

    def analyze_market(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> Optional[Order]:
        """
        Market makers don't use analyze_market in the traditional sense.
        This is here to satisfy the abstract base class.

        Returns:
            None (market makers place bid/ask pairs, not single orders)
        """
        return None

    def should_adjust_position(
        self,
        position: Position,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> Optional[Order]:
        """
        Market makers manage positions through inventory management.

        Returns:
            None
        """
        return None

    def get_strategy_stats(self) -> Dict:
        """
        Get market making statistics.

        Returns:
            Dictionary with strategy stats
        """
        total_inventory = sum(abs(shares) for shares in self.inventory.values())

        return {
            "strategy": self.name,
            "num_positions": len(self.positions),
            "num_outcomes_with_inventory": len(self.inventory),
            "total_inventory": total_inventory,
            "max_inventory": self.max_inventory,
            "daily_pnl": self.daily_pnl,
            "stopped": self.stopped,
            "min_spread": self.min_spread,
            "active_orders": len(self.active_orders)
        }
