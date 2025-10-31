"""
Real-time temperature monitoring for target day (J-0).
Monitors historical weather data and triggers position adjustments.
"""

import time
import asyncio
from typing import Optional, Dict, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from .logger import get_logger, log_forecast_change
from ..clients.weather import WeatherClient
from ..models.market import TemperatureMarket

logger = get_logger()


@dataclass
class TemperatureReading:
    """Represents a temperature reading at a specific time."""
    timestamp: datetime
    temperature: float
    current_max: float


class RealtimeMonitor:
    """
    Monitors real-time temperature observations on target day.
    Polls weather API every second to detect temperature changes.
    """

    def __init__(
        self,
        weather_client: WeatherClient,
        check_interval: int = 1  # seconds
    ):
        """
        Initialize realtime monitor.

        Args:
            weather_client: Weather.com client
            check_interval: Seconds between checks (default 1)
        """
        self.weather_client = weather_client
        self.check_interval = check_interval

        self.previous_max: Optional[float] = None
        self.readings: list[TemperatureReading] = []
        self.monitoring = False

        logger.info(
            f"RealtimeMonitor initialized | "
            f"Check interval: {check_interval}s"
        )

    def is_target_day(self, market: TemperatureMarket) -> bool:
        """
        Check if today is the target day for a market.

        Args:
            market: Temperature market

        Returns:
            True if today is the target day
        """
        today = datetime.now().date()
        target_date = market.target_date.date()

        return today == target_date

    async def get_current_max(self) -> Optional[float]:
        """
        Get current maximum temperature observed today.

        Returns:
            Current max temperature or None if no data
        """
        try:
            data = await self.weather_client.get_historical_today()
            current_max = data.get("current_max")

            if current_max is not None:
                # Store reading
                reading = TemperatureReading(
                    timestamp=datetime.now(),
                    temperature=data.get("latest_temp", current_max),
                    current_max=current_max
                )
                self.readings.append(reading)

                logger.debug(
                    f"Current max: {current_max}°F "
                    f"({data.get('observation_count', 0)} observations)"
                )

            return current_max

        except Exception as e:
            logger.error(f"Failed to get current max: {e}")
            return None

    def detect_max_change(
        self,
        new_max: float,
        threshold: float = 0.5
    ) -> bool:
        """
        Detect if maximum temperature has changed significantly.

        Args:
            new_max: New maximum temperature
            threshold: Minimum change to be significant (°F)

        Returns:
            True if change is significant
        """
        if self.previous_max is None:
            self.previous_max = new_max
            logger.info(f"Initial max temperature: {new_max}°F")
            return False

        change = abs(new_max - self.previous_max)

        if change >= threshold:
            logger.warning(
                f"Temperature max changed: {self.previous_max}°F -> {new_max}°F "
                f"(Δ{new_max - self.previous_max:+.1f}°F)"
            )

            log_forecast_change(
                date=datetime.now().strftime("%Y-%m-%d"),
                old_temp=self.previous_max,
                new_temp=new_max,
                significance="MAJOR" if change >= 2.0 else "MODERATE"
            )

            self.previous_max = new_max
            return True

        return False

    async def monitor_until_end_of_day(
        self,
        market: TemperatureMarket,
        on_change_callback: Optional[Callable[[float, float], None]] = None,
        end_hour: int = 23  # Stop at 11 PM
    ) -> Dict:
        """
        Monitor temperature continuously until end of day.

        Args:
            market: Temperature market being monitored
            on_change_callback: Function to call when temp changes (old_max, new_max)
            end_hour: Hour to stop monitoring (default 23 = 11 PM)

        Returns:
            Dictionary with monitoring results
        """
        logger.info(
            f"Starting realtime monitoring for market {market.market_id[:8]}... "
            f"until {end_hour}:00"
        )

        self.monitoring = True
        self.readings.clear()
        self.previous_max = None

        num_checks = 0
        num_changes = 0
        start_time = datetime.now()

        try:
            while self.monitoring:
                # Check if we should stop (end of day)
                now = datetime.now()

                if now.hour >= end_hour:
                    logger.info("End hour reached, stopping monitoring")
                    break

                # Get current max (async)
                current_max = await self.get_current_max()

                if current_max is not None:
                    num_checks += 1

                    # Detect change
                    if self.detect_max_change(current_max):
                        num_changes += 1

                        # Trigger callback
                        if on_change_callback and self.previous_max is not None:
                            try:
                                # Get previous value (before it was updated)
                                old_max = self.readings[-2].current_max if len(self.readings) >= 2 else self.previous_max
                                on_change_callback(old_max, current_max)
                            except Exception as e:
                                logger.error(f"Callback error: {e}")

                # Sleep until next check
                await asyncio.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")

        except Exception as e:
            logger.error(f"Error during monitoring: {e}")

        finally:
            self.monitoring = False

        # Calculate results
        duration = (datetime.now() - start_time).total_seconds()
        final_max = self.readings[-1].current_max if self.readings else None

        results = {
            "start_time": start_time,
            "end_time": datetime.now(),
            "duration_seconds": duration,
            "num_checks": num_checks,
            "num_changes": num_changes,
            "num_readings": len(self.readings),
            "final_max": final_max,
            "initial_max": self.readings[0].current_max if self.readings else None
        }

        logger.info(
            f"Monitoring completed | "
            f"Duration: {duration:.0f}s | "
            f"Checks: {num_checks} | "
            f"Changes: {num_changes} | "
            f"Final max: {final_max}°F"
        )

        return results

    def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        logger.info("Stopping realtime monitoring")
        self.monitoring = False

    def get_temperature_trend(self, window_minutes: int = 30) -> Optional[str]:
        """
        Analyze temperature trend over recent window.

        Args:
            window_minutes: Window to analyze (default 30 minutes)

        Returns:
            Trend: "RISING", "FALLING", "STABLE", or None
        """
        if len(self.readings) < 2:
            return None

        # Get readings from last N minutes
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_readings = [
            r for r in self.readings
            if r.timestamp >= cutoff_time
        ]

        if len(recent_readings) < 2:
            return None

        # Compare first and last
        first_max = recent_readings[0].current_max
        last_max = recent_readings[-1].current_max

        change = last_max - first_max

        if abs(change) < 0.5:
            return "STABLE"
        elif change > 0:
            return "RISING"
        else:
            return "FALLING"

    def get_monitoring_stats(self) -> Dict:
        """
        Get statistics about current monitoring session.

        Returns:
            Dictionary with stats
        """
        if not self.readings:
            return {
                "status": "no_data",
                "num_readings": 0
            }

        temps = [r.current_max for r in self.readings]

        return {
            "status": "monitoring" if self.monitoring else "stopped",
            "num_readings": len(self.readings),
            "current_max": self.readings[-1].current_max,
            "min_observed": min(temps),
            "max_observed": max(temps),
            "trend": self.get_temperature_trend(),
            "last_update": self.readings[-1].timestamp.isoformat()
        }


class PositionAdjuster:
    """
    Handles position adjustments based on realtime temperature changes.
    Works with trading strategies to quickly react to changes.
    """

    def __init__(
        self,
        strategy,
        market: TemperatureMarket
    ):
        """
        Initialize position adjuster.

        Args:
            strategy: Trading strategy (PositionTaker or MarketMaker)
            market: Temperature market
        """
        self.strategy = strategy
        self.market = market

        logger.info(
            f"PositionAdjuster initialized for market {market.market_id[:8]}..."
        )

    def adjust_for_temperature(
        self,
        old_max: float,
        new_max: float
    ) -> bool:
        """
        Adjust positions based on temperature change.

        Args:
            old_max: Previous maximum temperature
            new_max: New maximum temperature

        Returns:
            True if positions were adjusted
        """
        logger.info(
            f"Adjusting positions: {old_max}°F -> {new_max}°F"
        )

        # Find old and new outcomes
        old_outcome = self.market.get_outcome_by_temperature(old_max)
        new_outcome = self.market.get_outcome_by_temperature(new_max)

        if old_outcome is None or new_outcome is None:
            logger.warning("Could not find matching outcomes")
            return False

        # If same outcome, no adjustment needed
        if old_outcome.token_id == new_outcome.token_id:
            logger.info("Temperature still in same range, no adjustment needed")
            return False

        adjusted = False

        # Close position on old outcome
        old_position = self.strategy.get_position_for_market(
            self.market.market_id,
            old_outcome.token_id
        )

        if old_position:
            logger.info(
                f"Closing position on {old_outcome.temperature_range.label}"
            )

            if self.strategy.client.close_position(old_position):
                adjusted = True
                logger.info("Old position closed successfully")
            else:
                logger.error("Failed to close old position")

        # Open position on new outcome (market order for speed)
        from ..models.trade import Order, OrderSide, OrderType

        new_order = Order(
            market_id=self.market.market_id,
            outcome_id=new_outcome.token_id,
            side=OrderSide.BUY,
            size=50.0,  # Quick position size
            price=new_outcome.price,
            order_type=OrderType.MARKET  # Use market order for speed
        )

        if self.strategy.execute_order(new_order):
            adjusted = True
            logger.info(
                f"New position opened on {new_outcome.temperature_range.label}"
            )
        else:
            logger.error("Failed to open new position")

        return adjusted

    def end_of_day_cleanup(self, hours_before_close: int = 2) -> None:
        """
        Cleanup positions near end of day.

        Args:
            hours_before_close: Hours before market close to start cleanup
        """
        logger.info(
            f"Starting end-of-day cleanup "
            f"({hours_before_close}h before close)"
        )

        # Stop market making if active
        if hasattr(self.strategy, 'stopped'):
            self.strategy.stopped = True
            logger.info("Stopped market making")

        # Close losing positions, keep winning position
        current_max = self.strategy.client.get_balance()  # Placeholder

        # Get all positions for this market
        market_positions = [
            p for p in self.strategy.positions
            if p.market_id == self.market.market_id
        ]

        for position in market_positions:
            outcome = self.market.get_outcome_by_token_id(position.outcome_id)

            if outcome:
                # Keep position if it's likely to win
                # (will be implemented with actual temp check)
                logger.info(
                    f"Position on {outcome.temperature_range.label}: "
                    f"{position.shares:.2f} shares"
                )
