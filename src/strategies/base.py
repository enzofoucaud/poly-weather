"""
Base strategy class for trading strategies.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime
import asyncio

from ..models.market import TemperatureMarket, WeatherForecast
from ..models.trade import Order, Position
from ..clients.polymarket import PolymarketClient
from ..clients.polymarket_simulator import PolymarketSimulator
from ..utils.logger import get_logger

logger = get_logger()


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    def __init__(
        self,
        client: PolymarketClient | PolymarketSimulator,
        name: str = "BaseStrategy"
    ):
        """
        Initialize strategy.

        Args:
            client: Polymarket client or simulator
            name: Strategy name
        """
        self.client = client
        self.name = name
        self.active_orders: Dict[str, Order] = {}
        self.positions: List[Position] = []

        logger.info(f"Strategy '{name}' initialized")

    @abstractmethod
    async def analyze_market(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> Optional[Order]:
        """
        Analyze a market and decide if/how to trade.

        Args:
            market: Temperature market to analyze
            forecast: Weather forecast for the target date

        Returns:
            Order to execute, or None
        """
        pass

    @abstractmethod
    async def should_adjust_position(
        self,
        position: Position,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> Optional[Order]:
        """
        Determine if a position should be adjusted.

        Args:
            position: Current position
            market: Market information
            forecast: Updated forecast

        Returns:
            Order to adjust position, or None
        """
        pass

    async def execute_order(self, order: Order) -> bool:
        """
        Execute an order through the client.

        Args:
            order: Order to execute

        Returns:
            True if successful
        """
        try:
            order_id = await self.client.place_order(order)
            order.order_id = order_id
            order.timestamp = datetime.now()

            # Track active order
            self.active_orders[order_id] = order

            logger.info(f"[{self.name}] Order executed: {order_id}")
            return True

        except Exception as e:
            logger.error(f"[{self.name}] Failed to execute order: {e}")
            return False

    async def update_positions(self) -> None:
        """Update positions from the client."""
        try:
            self.positions = await self.client.get_positions()
            logger.debug(f"[{self.name}] Updated {len(self.positions)} positions")

        except Exception as e:
            logger.error(f"[{self.name}] Failed to update positions: {e}")

    def get_position_for_market(
        self,
        market_id: str,
        outcome_id: str
    ) -> Optional[Position]:
        """
        Get position for a specific market outcome.

        Args:
            market_id: Market identifier
            outcome_id: Outcome identifier

        Returns:
            Position or None
        """
        for position in self.positions:
            if position.market_id == market_id and position.outcome_id == outcome_id:
                return position
        return None

    async def close_all_positions(self) -> int:
        """
        Close all open positions.

        Returns:
            Number of positions closed
        """
        closed = 0

        for position in self.positions:
            try:
                if await self.client.close_position(position):
                    closed += 1
                    logger.info(
                        f"[{self.name}] Closed position: {position.outcome_id[:8]}..."
                    )
            except Exception as e:
                logger.error(
                    f"[{self.name}] Failed to close position "
                    f"{position.outcome_id[:8]}...: {e}"
                )

        return closed

    def get_total_exposure(self) -> float:
        """
        Calculate total exposure across all positions.

        Returns:
            Total exposure in USDC
        """
        return sum(p.current_value() for p in self.positions)

    def get_total_pnl(self) -> float:
        """
        Calculate total unrealized PnL.

        Returns:
            Total PnL in USDC
        """
        return sum(p.calculate_unrealized_pnl() for p in self.positions)
