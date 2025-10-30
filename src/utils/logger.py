"""
Logging configuration using Loguru.
Provides structured logging with file rotation and console output.
"""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional


def setup_logger(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_rotation: str = "daily",
    log_retention_days: int = 30,
    log_dir: str = "logs",
    dry_run_mode: bool = True
) -> None:
    """
    Configure the global logger instance.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_to_file: Whether to log to files
        log_rotation: File rotation strategy (daily, weekly, or size like "10 MB")
        log_retention_days: Number of days to keep old logs
        log_dir: Directory for log files
        dry_run_mode: Whether running in dry-run mode (affects log format)
    """
    # Remove default logger
    logger.remove()

    # Determine log format
    mode_prefix = "[DRY-RUN] " if dry_run_mode else "[LIVE] "

    # Console format with colors
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        f"<yellow>{mode_prefix}</yellow>"
        "<level>{message}</level>"
    )

    # File format (no colors)
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        f"{mode_prefix}"
        "{message}"
    )

    # Add console handler
    logger.add(
        sys.stdout,
        format=console_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # Add file handler if enabled
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Parse rotation parameter
        if log_rotation == "daily":
            rotation = "00:00"  # Rotate at midnight
        elif log_rotation == "weekly":
            rotation = "1 week"
        else:
            # Assume it's a size (e.g., "10 MB")
            rotation = log_rotation

        # Main log file
        logger.add(
            log_path / "bot_{time:YYYY-MM-DD}.log",
            format=file_format,
            level=log_level,
            rotation=rotation,
            retention=f"{log_retention_days} days",
            compression="zip",
            backtrace=True,
            diagnose=True
        )

        # Separate error log file
        logger.add(
            log_path / "errors_{time:YYYY-MM-DD}.log",
            format=file_format,
            level="ERROR",
            rotation=rotation,
            retention=f"{log_retention_days} days",
            compression="zip",
            backtrace=True,
            diagnose=True
        )

        # Trade-specific log file
        logger.add(
            log_path / "trades_{time:YYYY-MM-DD}.log",
            format=file_format,
            level="INFO",
            rotation=rotation,
            retention=f"{log_retention_days * 2} days",  # Keep trade logs longer
            compression="zip",
            filter=lambda record: "TRADE" in record["extra"]
        )

    logger.info(f"Logger initialized with level={log_level}, dry_run_mode={dry_run_mode}")


def get_logger():
    """
    Get the configured logger instance.

    Returns:
        The global logger instance
    """
    return logger


def log_trade(
    action: str,
    market_id: str,
    outcome_id: str,
    price: float,
    size: float,
    details: Optional[dict] = None
) -> None:
    """
    Log a trade with structured information.

    Args:
        action: Trade action (BUY, SELL, etc.)
        market_id: Market identifier
        outcome_id: Outcome identifier
        price: Trade price
        size: Trade size
        details: Additional details to log
    """
    log_data = {
        "action": action,
        "market_id": market_id,
        "outcome_id": outcome_id,
        "price": price,
        "size": size,
    }

    if details:
        log_data.update(details)

    logger.bind(TRADE=True).info(
        f"TRADE | {action} | Market: {market_id[:8]}... | "
        f"Outcome: {outcome_id[:8]}... | Price: {price:.4f} | Size: {size:.2f}",
        **log_data
    )


def log_position_update(
    market_id: str,
    outcome_id: str,
    shares: float,
    avg_entry_price: float,
    current_price: float,
    pnl: float
) -> None:
    """
    Log a position update with structured information.

    Args:
        market_id: Market identifier
        outcome_id: Outcome identifier
        shares: Number of shares held
        avg_entry_price: Average entry price
        current_price: Current market price
        pnl: Unrealized PnL
    """
    pnl_sign = "+" if pnl >= 0 else ""
    logger.info(
        f"POSITION | Market: {market_id[:8]}... | "
        f"Shares: {shares:.2f} | Entry: {avg_entry_price:.4f} | "
        f"Current: {current_price:.4f} | PnL: {pnl_sign}{pnl:.2f} USDC"
    )


def log_forecast_change(
    date: str,
    old_temp: float,
    new_temp: float,
    significance: str = "MINOR"
) -> None:
    """
    Log a weather forecast change.

    Args:
        date: Target date
        old_temp: Previous forecast temperature
        new_temp: New forecast temperature
        significance: Change significance (MINOR, MODERATE, MAJOR)
    """
    change = new_temp - old_temp
    change_sign = "+" if change >= 0 else ""

    logger.warning(
        f"FORECAST CHANGE [{significance}] | Date: {date} | "
        f"Old: {old_temp:.1f}°F | New: {new_temp:.1f}°F | "
        f"Change: {change_sign}{change:.1f}°F"
    )


def log_risk_alert(
    alert_type: str,
    message: str,
    current_value: float,
    limit: float,
    action: str = "MONITORING"
) -> None:
    """
    Log a risk management alert.

    Args:
        alert_type: Type of alert (EXPOSURE, LOSS, INVENTORY, etc.)
        message: Alert message
        current_value: Current value that triggered alert
        limit: Configured limit
        action: Action taken (MONITORING, PAUSED, STOPPED)
    """
    percentage = (current_value / limit * 100) if limit > 0 else 0

    logger.warning(
        f"RISK ALERT [{alert_type}] | {message} | "
        f"Current: {current_value:.2f} | Limit: {limit:.2f} | "
        f"Usage: {percentage:.1f}% | Action: {action}"
    )


def log_market_analysis(
    market_id: str,
    predicted_temp: float,
    selected_outcome: str,
    confidence: float,
    edge: float,
    position_size: float
) -> None:
    """
    Log market analysis results.

    Args:
        market_id: Market identifier
        predicted_temp: Predicted temperature
        selected_outcome: Selected outcome label
        confidence: Confidence score (0-1)
        edge: Calculated edge
        position_size: Recommended position size
    """
    logger.info(
        f"ANALYSIS | Market: {market_id[:8]}... | "
        f"Predicted: {predicted_temp:.1f}°F | Outcome: {selected_outcome} | "
        f"Confidence: {confidence:.2f} | Edge: {edge:.2f} | "
        f"Size: {position_size:.2f} USDC"
    )
