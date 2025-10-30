"""
Polymarket simulator for dry-run mode.
Simulates trading without executing real trades.
"""

import uuid
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

from ..utils.logger import get_logger, log_trade
from ..models.market import TemperatureMarket, PolymarketOutcome
from ..models.trade import Order, Position, Trade, OrderSide, OrderStatus

logger = get_logger()


class PolymarketSimulator:
    """
    Simulates Polymarket trading for testing and dry-run mode.
    Implements the same interface as PolymarketClient but doesn't execute real trades.
    """

    def __init__(
        self,
        initial_balance: float = 1000.0,
        transaction_fee: float = 0.002  # 0.2%
    ):
        """
        Initialize Polymarket simulator.

        Args:
            initial_balance: Starting USDC balance
            transaction_fee: Transaction fee percentage (0.002 = 0.2%)
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.transaction_fee = transaction_fee

        # Track simulated state
        self.orders: Dict[str, Dict] = {}  # order_id -> order_data
        self.positions: Dict[str, Position] = {}  # position_key -> Position
        self.trades: List[Trade] = []
        self.market_prices: Dict[str, float] = {}  # token_id -> current_price

        logger.info(
            f"PolymarketSimulator initialized | "
            f"Balance: {initial_balance:.2f} USDC | "
            f"Fee: {transaction_fee * 100:.2f}%"
        )

    def get_balance(self) -> float:
        """Get current USDC balance."""
        return self.balance

    def setup_allowances(self, amount: Optional[float] = None) -> bool:
        """Simulate allowance setup (always succeeds in simulation)."""
        logger.info("[SIMULATOR] Allowances setup (simulated)")
        return True

    def get_temperature_markets(
        self,
        city: str = "NYC",
        active_only: bool = True
    ) -> List[TemperatureMarket]:
        """
        Get temperature markets.
        In simulation mode, this would return mock markets or fetch real market data
        without executing trades.

        Args:
            city: City name
            active_only: Only return active markets

        Returns:
            List of TemperatureMarket objects
        """
        logger.info(f"[SIMULATOR] Fetching markets for {city}")
        # In a real implementation, you might fetch actual market data
        # but never execute trades
        return []

    def get_market_orderbook(
        self,
        token_id: str,
        side: Optional[str] = None
    ) -> Dict:
        """
        Get orderbook for a token.
        Returns simulated or real market data.

        Args:
            token_id: Token identifier
            side: Optional side filter

        Returns:
            Orderbook data
        """
        # Use cached price or default
        price = self.market_prices.get(token_id, 0.5)

        # Simulate spread
        spread = 0.02  # 2%
        best_bid = price - (spread / 2)
        best_ask = price + (spread / 2)

        return {
            "bids": [{"price": best_bid, "size": 1000}],
            "asks": [{"price": best_ask, "size": 1000}],
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread
        }

    def place_order(self, order: Order) -> str:
        """
        Simulate placing an order.

        Args:
            order: Order to place

        Returns:
            Simulated order ID
        """
        order_id = f"sim_{uuid.uuid4().hex[:8]}"

        # Check if we have enough balance
        if order.side == OrderSide.BUY:
            cost = order.size * order.price
            fee = cost * self.transaction_fee
            total_cost = cost + fee

            if total_cost > self.balance:
                logger.error(
                    f"[SIMULATOR] Insufficient balance: {self.balance:.2f} < {total_cost:.2f}"
                )
                raise ValueError("Insufficient balance")

            # Deduct from balance
            self.balance -= total_cost

            # Create or update position
            self._update_position(
                market_id=order.market_id,
                outcome_id=order.outcome_id,
                shares=order.size / order.price,  # Shares = size / price
                avg_price=order.price,
                delta_shares=order.size / order.price
            )

        else:  # SELL
            # Find position
            position_key = f"{order.market_id}:{order.outcome_id}"
            position = self.positions.get(position_key)

            if not position or position.shares < (order.size / order.price):
                logger.error("[SIMULATOR] Insufficient shares to sell")
                raise ValueError("Insufficient shares")

            # Calculate proceeds
            proceeds = order.size * order.price
            fee = proceeds * self.transaction_fee
            net_proceeds = proceeds - fee

            # Add to balance
            self.balance += net_proceeds

            # Update position
            self._update_position(
                market_id=order.market_id,
                outcome_id=order.outcome_id,
                shares=0,  # Will be recalculated
                avg_price=position.avg_entry_price,
                delta_shares=-(order.size / order.price)
            )

        # Store order
        self.orders[order_id] = {
            "order_id": order_id,
            "order": order,
            "status": OrderStatus.FILLED,
            "timestamp": datetime.now(),
            "filled_price": order.price,
            "fee": order.size * order.price * self.transaction_fee
        }

        # Log the trade
        log_trade(
            action=order.side.value,
            market_id=order.market_id,
            outcome_id=order.outcome_id,
            price=order.price,
            size=order.size,
            details={"order_id": order_id, "simulator": True}
        )

        logger.info(
            f"[SIMULATOR] Order filled: {order.side.value} {order.size:.2f} "
            f"@ {order.price:.4f} | ID: {order_id} | "
            f"Balance: {self.balance:.2f} USDC"
        )

        return order_id

    def _update_position(
        self,
        market_id: str,
        outcome_id: str,
        shares: float,
        avg_price: float,
        delta_shares: float
    ) -> None:
        """
        Update or create a position.

        Args:
            market_id: Market ID
            outcome_id: Outcome/token ID
            shares: Total shares (ignored if updating)
            avg_price: Average entry price
            delta_shares: Change in shares (positive for buy, negative for sell)
        """
        position_key = f"{market_id}:{outcome_id}"

        if position_key in self.positions:
            position = self.positions[position_key]

            # Update shares
            new_shares = position.shares + delta_shares

            if new_shares <= 0:
                # Position closed
                del self.positions[position_key]
                logger.debug(f"[SIMULATOR] Position closed: {position_key}")
            else:
                # Update position
                position.shares = new_shares
                # Keep avg_entry_price the same for now
                # (in reality, you'd calculate weighted average)
                logger.debug(f"[SIMULATOR] Position updated: {position_key} -> {new_shares:.2f} shares")

        else:
            # Create new position
            if delta_shares > 0:
                position = Position(
                    market_id=market_id,
                    outcome_id=outcome_id,
                    shares=delta_shares,
                    avg_entry_price=avg_price,
                    current_price=avg_price
                )
                self.positions[position_key] = position
                logger.debug(f"[SIMULATOR] Position created: {position_key} -> {delta_shares:.2f} shares")

    def cancel_order(self, order_id: str) -> bool:
        """Simulate canceling an order."""
        if order_id in self.orders:
            self.orders[order_id]["status"] = OrderStatus.CANCELLED
            logger.info(f"[SIMULATOR] Order cancelled: {order_id}")
            return True

        logger.warning(f"[SIMULATOR] Order not found: {order_id}")
        return False

    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get simulated order status."""
        if order_id in self.orders:
            return self.orders[order_id]["status"]
        return OrderStatus.FAILED

    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self.positions.values())

    def close_position(
        self,
        position: Position,
        price: Optional[float] = None
    ) -> bool:
        """
        Close a position by selling all shares.

        Args:
            position: Position to close
            price: Sell price (uses current price if None)

        Returns:
            True if successful
        """
        try:
            sell_price = price if price else position.current_price

            # Create sell order
            order = Order(
                market_id=position.market_id,
                outcome_id=position.outcome_id,
                side=OrderSide.SELL,
                size=position.shares * sell_price,  # Size in USDC
                price=sell_price
            )

            self.place_order(order)
            return True

        except Exception as e:
            logger.error(f"[SIMULATOR] Failed to close position: {e}")
            return False

    def update_market_price(self, token_id: str, price: float) -> None:
        """
        Update simulated market price for a token.
        Used to track real market prices during simulation.

        Args:
            token_id: Token identifier
            price: Current market price
        """
        self.market_prices[token_id] = price

        # Update position prices
        for position in self.positions.values():
            if position.outcome_id == token_id:
                position.update_price(price)

    def get_performance_report(self) -> Dict:
        """
        Get performance report for the simulation.

        Returns:
            Dictionary with performance metrics
        """
        # Calculate total position value
        total_position_value = sum(
            p.current_value() for p in self.positions.values()
        )

        # Calculate total PnL
        unrealized_pnl = sum(
            p.calculate_unrealized_pnl() for p in self.positions.values()
        )

        realized_pnl = self.balance - self.initial_balance

        total_pnl = realized_pnl + unrealized_pnl

        # Count trades
        num_trades = len(self.orders)

        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.balance,
            "position_value": total_position_value,
            "total_value": self.balance + total_position_value,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "pnl_percentage": (total_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0,
            "num_trades": num_trades,
            "num_positions": len(self.positions)
        }

    def reset(self) -> None:
        """Reset simulator to initial state."""
        self.balance = self.initial_balance
        self.orders.clear()
        self.positions.clear()
        self.trades.clear()
        self.market_prices.clear()

        logger.info("[SIMULATOR] Reset to initial state")
