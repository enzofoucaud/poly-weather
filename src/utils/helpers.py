"""
Helper utilities for the trading bot.
"""

from datetime import datetime, timedelta
from typing import Optional


def get_confidence_score(forecast_date: datetime, reference_date: Optional[datetime] = None) -> float:
    """
    Calculate confidence score based on how far ahead the forecast is.

    Confidence decreases linearly as we go further into the future:
    - J-0 (today): 0.95
    - J-1: 0.85
    - J-2: 0.75
    - J-3: 0.65
    - J-4+: continues decreasing by 0.10 per day

    Args:
        forecast_date: The date being forecasted
        reference_date: The reference date (defaults to now)

    Returns:
        Confidence score between 0.5 and 0.95
    """
    if reference_date is None:
        reference_date = datetime.now()

    # Calculate days ahead
    delta = forecast_date.replace(hour=0, minute=0, second=0, microsecond=0) - \
            reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    days_ahead = delta.days

    # Calculate confidence
    confidence = 0.95 - (days_ahead * 0.10)

    # Clamp between 0.5 and 0.95
    return max(0.5, min(0.95, confidence))


def detect_forecast_change(old_max: float, new_max: float, threshold: float = 1.0) -> bool:
    """
    Detect if the forecast has changed significantly.

    Args:
        old_max: Previous forecast maximum temperature
        new_max: New forecast maximum temperature
        threshold: Minimum change to be considered significant (default 1°F)

    Returns:
        True if change is significant
    """
    return abs(new_max - old_max) >= threshold


def get_forecast_change_significance(old_max: float, new_max: float) -> str:
    """
    Categorize the significance of a forecast change.

    Args:
        old_max: Previous forecast maximum temperature
        new_max: New forecast maximum temperature

    Returns:
        Significance level: "MINOR", "MODERATE", or "MAJOR"
    """
    change = abs(new_max - old_max)

    if change < 1.0:
        return "MINOR"
    elif change < 3.0:
        return "MODERATE"
    else:
        return "MAJOR"


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (celsius * 9/5) + 32


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - 32) * 5/9


def format_temperature(temp: float, unit: str = "F", decimals: int = 1) -> str:
    """
    Format temperature for display.

    Args:
        temp: Temperature value
        unit: Unit ("F" or "C")
        decimals: Number of decimal places

    Returns:
        Formatted string like "62.5°F"
    """
    return f"{temp:.{decimals}f}°{unit}"


def is_market_hour() -> bool:
    """
    Check if it's currently market hours (when trading is most active).
    For weather markets, this might be during business hours.

    Returns:
        True if it's market hours
    """
    now = datetime.now()
    # Simple check: 9 AM to 9 PM EST
    return 9 <= now.hour < 21


def calculate_time_until(target_date: datetime) -> dict:
    """
    Calculate time remaining until a target date.

    Args:
        target_date: Target datetime

    Returns:
        Dictionary with days, hours, minutes, seconds
    """
    now = datetime.now()
    delta = target_date - now

    return {
        "days": delta.days,
        "hours": delta.seconds // 3600,
        "minutes": (delta.seconds % 3600) // 60,
        "seconds": delta.seconds % 60,
        "total_seconds": delta.total_seconds()
    }


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "2d 3h 15m" or "45m 30s"
    """
    if seconds < 0:
        return "expired"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 and days == 0:  # Only show seconds if less than a day
        parts.append(f"{secs}s")

    return " ".join(parts) if parts else "0s"


def round_to_nearest(value: float, nearest: float = 0.01) -> float:
    """
    Round a value to the nearest increment.

    Args:
        value: Value to round
        nearest: Increment to round to (default 0.01)

    Returns:
        Rounded value
    """
    return round(value / nearest) * nearest


def calculate_kelly_criterion(
    edge: float,
    odds: float,
    fraction: float = 0.25
) -> float:
    """
    Calculate position size using Kelly Criterion.

    Args:
        edge: Your edge (expected value - 1)
        odds: Decimal odds
        fraction: Fraction of Kelly to use (default 0.25 for conservative)

    Returns:
        Fraction of bankroll to bet (0-1)
    """
    if odds <= 1 or edge <= 0:
        return 0.0

    kelly = edge / (odds - 1)
    return max(0.0, min(1.0, kelly * fraction))


def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0
) -> float:
    """
    Calculate Sharpe ratio for a series of returns.

    Args:
        returns: List of period returns
        risk_free_rate: Risk-free rate (default 0)

    Returns:
        Sharpe ratio
    """
    if not returns or len(returns) < 2:
        return 0.0

    import numpy as np

    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate

    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)

    if std_excess == 0:
        return 0.0

    return mean_excess / std_excess


def format_pnl(pnl: float, decimals: int = 2) -> str:
    """
    Format PnL for display with + or - sign.

    Args:
        pnl: PnL value
        decimals: Number of decimal places

    Returns:
        Formatted string like "+15.50" or "-5.20"
    """
    sign = "+" if pnl >= 0 else ""
    return f"{sign}{pnl:.{decimals}f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format percentage for display.

    Args:
        value: Percentage value (e.g., 0.15 for 15%)
        decimals: Number of decimal places

    Returns:
        Formatted string like "15.0%"
    """
    return f"{value * 100:.{decimals}f}%"
