"""
Data models for Polymarket temperature markets.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class TemperatureUnit(Enum):
    """Temperature unit enum."""
    FAHRENHEIT = "F"
    CELSIUS = "C"


@dataclass
class TemperatureRange:
    """
    Represents a temperature range for a market outcome.

    Examples:
        - "61-62°F" -> min_temp=61, max_temp=62
        - "65°F or higher" -> min_temp=65, max_temp=None
        - "60°F or lower" -> min_temp=None, max_temp=60
    """
    label: str
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT

    def contains(self, temp: float) -> bool:
        """
        Check if a temperature falls within this range.

        Args:
            temp: Temperature to check

        Returns:
            True if temperature is within range
        """
        if self.min_temp is not None and temp < self.min_temp:
            return False
        if self.max_temp is not None and temp > self.max_temp:
            return False
        return True

    def __str__(self) -> str:
        return self.label

    @classmethod
    def from_label(cls, label: str) -> "TemperatureRange":
        """
        Parse a temperature range from a label string.

        Args:
            label: Label like "61-62°F", "65°F or higher"

        Returns:
            TemperatureRange instance
        """
        import re

        # Clean the label
        label = label.strip()

        # Pattern: "XX-YY°F" or "XX-YY"
        range_pattern = r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)"
        match = re.search(range_pattern, label)
        if match:
            min_temp = float(match.group(1))
            max_temp = float(match.group(2))
            return cls(label=label, min_temp=min_temp, max_temp=max_temp)

        # Pattern: "XX°F or higher" or "XX or higher"
        higher_pattern = r"(\d+\.?\d*)\s*(?:°F)?\s*or\s+(?:higher|above)"
        match = re.search(higher_pattern, label, re.IGNORECASE)
        if match:
            min_temp = float(match.group(1))
            return cls(label=label, min_temp=min_temp, max_temp=None)

        # Pattern: "XX°F or lower" or "XX or lower"
        lower_pattern = r"(\d+\.?\d*)\s*(?:°F)?\s*or\s+(?:lower|below)"
        match = re.search(lower_pattern, label, re.IGNORECASE)
        if match:
            max_temp = float(match.group(1))
            return cls(label=label, min_temp=None, max_temp=max_temp)

        # If no pattern matches, return with just the label
        return cls(label=label)


@dataclass
class PolymarketOutcome:
    """Represents a single outcome in a temperature market."""
    token_id: str
    price: float  # Current price (0-1 representing probability)
    temperature_range: TemperatureRange
    liquidity: float = 0.0
    volume_24h: float = 0.0

    # Market making data
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None

    def calculate_spread(self) -> float:
        """Calculate the bid-ask spread."""
        if self.best_bid is not None and self.best_ask is not None:
            self.spread = self.best_ask - self.best_bid
            return self.spread
        return 0.0

    def implied_probability(self) -> float:
        """Get the implied probability from the price."""
        return self.price

    def __str__(self) -> str:
        return f"{self.temperature_range.label} @ {self.price:.3f}"


@dataclass
class TemperatureMarket:
    """Represents a Polymarket temperature market."""
    market_id: str
    question: str
    target_date: datetime
    outcomes: List[PolymarketOutcome] = field(default_factory=list)

    # Market metadata
    volume_24h: float = 0.0
    liquidity: float = 0.0
    created_at: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Resolution data
    resolved: bool = False
    winning_outcome_id: Optional[str] = None
    actual_temperature: Optional[float] = None

    def get_outcome_by_token_id(self, token_id: str) -> Optional[PolymarketOutcome]:
        """Get an outcome by its token ID."""
        for outcome in self.outcomes:
            if outcome.token_id == token_id:
                return outcome
        return None

    def get_outcome_by_temperature(self, temp: float) -> Optional[PolymarketOutcome]:
        """
        Find the outcome that matches a given temperature.

        Args:
            temp: Temperature in Fahrenheit

        Returns:
            The matching outcome, or None
        """
        for outcome in self.outcomes:
            if outcome.temperature_range.contains(temp):
                return outcome
        return None

    def get_best_outcome_by_edge(self, predicted_temp: float) -> Optional[tuple[PolymarketOutcome, float]]:
        """
        Find the outcome with the best edge given a predicted temperature.

        Args:
            predicted_temp: Predicted temperature

        Returns:
            Tuple of (outcome, edge) or None
        """
        matching_outcome = self.get_outcome_by_temperature(predicted_temp)
        if matching_outcome is None:
            return None

        # Simple edge calculation: if we think it's 100% this outcome,
        # but market prices it at X, edge is (1 - X)
        edge = 1.0 - matching_outcome.price
        return (matching_outcome, edge)

    def total_probability(self) -> float:
        """
        Calculate the sum of all outcome probabilities.
        Should be close to 1.0 in efficient markets.
        If > 1.0, potential arbitrage opportunity.
        """
        return sum(outcome.price for outcome in self.outcomes)

    def is_arbitrageable(self, threshold: float = 0.05) -> bool:
        """
        Check if there's an arbitrage opportunity.

        Args:
            threshold: Minimum edge for arbitrage (e.g., 0.05 = 5%)

        Returns:
            True if total probability > 1 + threshold
        """
        total_prob = self.total_probability()
        return total_prob > (1.0 + threshold)

    def days_until_target(self) -> int:
        """Calculate days until target date."""
        from datetime import timezone

        # Normalize both datetimes to compare properly
        now = datetime.now()
        target = self.target_date

        # If target has timezone info, convert now to UTC
        if target.tzinfo is not None:
            now = now.replace(tzinfo=timezone.utc)
        # If target is naive but now would be aware, strip timezone
        else:
            target = target.replace(tzinfo=None)
            now = now.replace(tzinfo=None)

        delta = target.date() - now.date()
        return delta.days

    def is_target_day(self) -> bool:
        """Check if today is the target day."""
        return self.days_until_target() == 0

    def __str__(self) -> str:
        return f"Market {self.market_id[:8]}... | {self.question} | Target: {self.target_date.date()}"


@dataclass
class WeatherForecast:
    """Represents a weather forecast for a specific date."""
    date: datetime
    max_temperature: float
    min_temperature: Optional[float] = None
    confidence: float = 1.0  # 0-1 scale
    source: str = "weather.com"
    fetched_at: datetime = field(default_factory=datetime.now)

    def days_ahead(self) -> int:
        """Calculate how many days ahead this forecast is."""
        now = datetime.now()
        delta = self.date - now
        return delta.days

    def __str__(self) -> str:
        return f"Forecast for {self.date.date()}: {self.max_temperature:.1f}°F (confidence: {self.confidence:.2f})"
