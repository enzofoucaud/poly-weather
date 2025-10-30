"""
Data models for trading orders, positions, and trade history.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class OrderSide(Enum):
    """Order side enum."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type enum."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(Enum):
    """Order status enum."""
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class Order:
    """Represents a trading order."""
    market_id: str
    outcome_id: str
    side: OrderSide
    size: float  # Amount in USDC
    price: float  # Limit price (0-1), ignored for market orders
    order_type: OrderType = OrderType.LIMIT

    # Optional fields
    order_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    status: OrderStatus = OrderStatus.PENDING

    # Execution details
    filled_size: float = 0.0
    filled_price: Optional[float] = None
    fee: float = 0.0

    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED

    def is_active(self) -> bool:
        """Check if order is still active (pending or partially filled)."""
        return self.status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]

    def remaining_size(self) -> float:
        """Calculate remaining unfilled size."""
        return self.size - self.filled_size

    def total_cost(self) -> float:
        """Calculate total cost including fees."""
        if self.filled_price is not None:
            return (self.filled_size * self.filled_price) + self.fee
        return self.size * self.price

    def __str__(self) -> str:
        return (
            f"{self.side.value} {self.size:.2f} @ {self.price:.4f} "
            f"[{self.status.value}]"
        )


@dataclass
class Position:
    """Represents an open position in a market."""
    market_id: str
    outcome_id: str
    shares: float
    avg_entry_price: float

    # Current market data
    current_price: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

    # Optional metadata
    outcome_label: Optional[str] = None
    target_date: Optional[datetime] = None

    def calculate_unrealized_pnl(self) -> float:
        """
        Calculate unrealized PnL.

        Returns:
            PnL in USDC
        """
        return self.shares * (self.current_price - self.avg_entry_price)

    def calculate_pnl_percentage(self) -> float:
        """
        Calculate PnL as a percentage.

        Returns:
            PnL percentage
        """
        if self.avg_entry_price == 0:
            return 0.0
        return ((self.current_price - self.avg_entry_price) / self.avg_entry_price) * 100

    def current_value(self) -> float:
        """Calculate current position value in USDC."""
        return self.shares * self.current_price

    def cost_basis(self) -> float:
        """Calculate original cost basis in USDC."""
        return self.shares * self.avg_entry_price

    def update_price(self, new_price: float) -> None:
        """Update current price and timestamp."""
        self.current_price = new_price
        self.last_updated = datetime.now()

    def __str__(self) -> str:
        pnl = self.calculate_unrealized_pnl()
        pnl_pct = self.calculate_pnl_percentage()
        pnl_sign = "+" if pnl >= 0 else ""
        return (
            f"Position: {self.shares:.2f} shares @ {self.avg_entry_price:.4f} "
            f"| Current: {self.current_price:.4f} "
            f"| PnL: {pnl_sign}{pnl:.2f} ({pnl_pct:+.1f}%)"
        )


@dataclass
class Trade:
    """Represents a completed trade (for historical tracking)."""
    trade_id: str
    order_id: str
    market_id: str
    outcome_id: str
    side: OrderSide
    size: float
    price: float
    fee: float
    timestamp: datetime = field(default_factory=datetime.now)

    # Optional metadata
    outcome_label: Optional[str] = None
    strategy: Optional[str] = None  # e.g., "position_taking", "market_making"
    notes: Optional[str] = None

    def net_cost(self) -> float:
        """Calculate net cost (including fees)."""
        cost = self.size * self.price
        if self.side == OrderSide.BUY:
            return cost + self.fee
        else:
            return cost - self.fee

    def __str__(self) -> str:
        return (
            f"Trade {self.trade_id[:8]}... | {self.side.value} "
            f"{self.size:.2f} @ {self.price:.4f} | Fee: {self.fee:.4f}"
        )


@dataclass
class PositionSnapshot:
    """Snapshot of all positions at a point in time (for tracking)."""
    timestamp: datetime = field(default_factory=datetime.now)
    positions: list[Position] = field(default_factory=list)
    total_value: float = 0.0
    total_pnl: float = 0.0
    balance: float = 0.0  # Cash balance

    def calculate_totals(self) -> None:
        """Recalculate total value and PnL."""
        self.total_value = sum(p.current_value() for p in self.positions)
        self.total_pnl = sum(p.calculate_unrealized_pnl() for p in self.positions)

    def net_worth(self) -> float:
        """Calculate total net worth (positions + cash)."""
        return self.total_value + self.balance


@dataclass
class TradingSession:
    """Represents a trading session with performance metrics."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None

    # Performance metrics
    initial_balance: float = 0.0
    current_balance: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    # Trade statistics
    num_trades: int = 0
    num_wins: int = 0
    num_losses: int = 0
    total_fees: float = 0.0

    # High-level stats
    max_drawdown: float = 0.0
    peak_balance: float = 0.0

    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.num_trades == 0:
            return 0.0
        return (self.num_wins / self.num_trades) * 100

    def total_pnl(self) -> float:
        """Calculate total PnL (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl

    def pnl_percentage(self) -> float:
        """Calculate PnL as percentage of initial balance."""
        if self.initial_balance == 0:
            return 0.0
        return (self.total_pnl() / self.initial_balance) * 100

    def avg_win(self) -> float:
        """Calculate average win amount."""
        if self.num_wins == 0:
            return 0.0
        # This is a simplified calculation
        # In reality, you'd track individual trade PnLs
        return self.realized_pnl / self.num_wins if self.realized_pnl > 0 else 0.0

    def avg_loss(self) -> float:
        """Calculate average loss amount."""
        if self.num_losses == 0:
            return 0.0
        # Simplified calculation
        return self.realized_pnl / self.num_losses if self.realized_pnl < 0 else 0.0

    def update_drawdown(self) -> None:
        """Update max drawdown if current drawdown is larger."""
        current_total = self.current_balance + self.unrealized_pnl
        if current_total > self.peak_balance:
            self.peak_balance = current_total

        drawdown = self.peak_balance - current_total
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    def __str__(self) -> str:
        return (
            f"Session {self.session_id[:8]}... | "
            f"Balance: {self.current_balance:.2f} | "
            f"PnL: {self.total_pnl():.2f} ({self.pnl_percentage():.1f}%) | "
            f"Trades: {self.num_trades} | Win Rate: {self.win_rate():.1f}%"
        )
