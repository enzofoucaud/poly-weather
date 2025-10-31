"""
Main trading bot orchestrator.
Coordinates all components: weather client, Polymarket client, strategies, monitoring.
"""

import time
import signal
import sys
from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from threading import Thread, Event

from .clients.weather import WeatherClient
from .clients.polymarket import PolymarketClient
from .clients.polymarket_simulator import PolymarketSimulator
from .strategies.position_taker import PositionTakerStrategy
from .strategies.market_maker import MarketMakerStrategy
from .utils.realtime_monitor import RealtimeMonitor, PositionAdjuster
from .models.market import TemperatureMarket, WeatherForecast
from .config.settings import get_settings
from .utils.logger import setup_logger, get_logger, log_risk_alert

logger = get_logger()


class BotState(Enum):
    """Bot state machine states."""
    INITIALIZING = "INITIALIZING"
    SCANNING = "SCANNING"
    POSITIONING = "POSITIONING"
    MARKET_MAKING = "MARKET_MAKING"
    DAY_OF_MONITORING = "DAY_OF_MONITORING"
    WAITING_RESOLUTION = "WAITING_RESOLUTION"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class TradingBot:
    """
    Main trading bot that orchestrates all components.

    Responsibilities:
    - Manage bot lifecycle and state
    - Coordinate weather and Polymarket clients
    - Execute trading strategies
    - Handle real-time monitoring on target day
    - Manage multiple markets concurrently
    """

    def __init__(self, dry_run: bool = True):
        """
        Initialize trading bot.

        Args:
            dry_run: If True, use simulator instead of real trading
        """
        # Load settings
        self.settings = get_settings()

        # Initialize logger
        setup_logger(
            log_level=self.settings.log_level,
            log_to_file=self.settings.log_to_file,
            log_rotation=self.settings.log_rotation,
            log_retention_days=self.settings.log_retention_days,
            dry_run_mode=dry_run
        )

        logger.info("=" * 60)
        logger.info("Initializing Poly-Weather Trading Bot")
        logger.info("=" * 60)

        self.dry_run = dry_run
        self.state = BotState.INITIALIZING
        self.running = False
        self.shutdown_event = Event()

        # Initialize clients
        self._init_clients()

        # Initialize strategies
        self._init_strategies()

        # State tracking
        self.active_markets: Dict[str, TemperatureMarket] = {}
        self.market_states: Dict[str, BotState] = {}
        self.monitors: Dict[str, RealtimeMonitor] = {}

        # Threading
        self.threads: List[Thread] = []

        logger.info(f"Bot initialized | Dry run: {dry_run}")

    def _init_clients(self) -> None:
        """Initialize weather and Polymarket clients."""
        # Weather client
        self.weather_client = WeatherClient(
            api_key=self.settings.weather_api_key,
            geocode=self.settings.weather_geocode,
            location_id=self.settings.weather_location_id
        )

        # Polymarket client or simulator
        if self.dry_run:
            self.poly_client = PolymarketSimulator(
                initial_balance=self.settings.dry_run_initial_balance,
                transaction_fee=self.settings.dry_run_transaction_fee
            )
            logger.info("Using Polymarket Simulator (dry-run mode)")
        else:
            self.poly_client = PolymarketClient(
                private_key=self.settings.polymarket_private_key,
                chain_id=self.settings.chain_id,
                proxy_address=self.settings.polymarket_proxy_address,
                dry_run=False
            )
            logger.info("Using Polymarket Client (LIVE mode)")

    def _init_strategies(self) -> None:
        """Initialize trading strategies."""
        # Position taker strategy
        if self.settings.enable_position_taking:
            self.position_taker = PositionTakerStrategy(
                client=self.poly_client,
                max_position_size=self.settings.max_position_size,
                max_exposure_per_market=self.settings.max_exposure_per_market,
                advance_days=self.settings.advance_days
            )
            logger.info("Position Taking strategy enabled")
        else:
            self.position_taker = None
            logger.info("Position Taking strategy disabled")

        # Market maker strategy
        if self.settings.enable_market_making:
            self.market_maker = MarketMakerStrategy(
                client=self.poly_client,
                min_spread=self.settings.min_spread,
                max_daily_loss=self.settings.max_daily_loss
            )
            logger.info("Market Making strategy enabled")
        else:
            self.market_maker = None
            logger.info("Market Making strategy disabled")

    def scan_markets(self) -> List[TemperatureMarket]:
        """
        Scan for temperature markets.

        Automatically discovers markets if no slugs are specified.

        Returns:
            List of active temperature markets
        """
        logger.info("Scanning for temperature markets...")

        try:
            all_markets = []
            slugs_to_fetch = []

            # 1. Check if multiple event slugs are manually provided
            if self.settings.event_slugs:
                slugs_to_fetch = [s.strip() for s in self.settings.event_slugs.split(',') if s.strip()]
                logger.info(f"Using manually specified event slugs: {slugs_to_fetch}")

            # 2. Check if single event_slug is provided
            elif self.settings.event_slug:
                slugs_to_fetch = [self.settings.event_slug]
                logger.info(f"Using manually specified event slug: {self.settings.event_slug}")

            # 3. Auto-discover markets if no slugs specified
            else:
                logger.info(f"No event slugs specified, auto-discovering markets for {self.settings.target_city}")
                from src.clients.market_discovery import MarketDiscovery

                discovery = MarketDiscovery(city=self.settings.target_city)
                slugs_to_fetch = discovery.get_event_slugs_for_next_days(
                    days_ahead=self.settings.advance_days
                )

                if slugs_to_fetch:
                    logger.info(f"Auto-discovered {len(slugs_to_fetch)} market(s): {slugs_to_fetch}")
                else:
                    logger.warning("No temperature markets found through auto-discovery")

            # Fetch markets for all slugs
            for slug in slugs_to_fetch:
                try:
                    markets = self.poly_client.get_temperature_markets(
                        city=self.settings.target_city,
                        active_only=True,
                        event_slug=slug
                    )
                    all_markets.extend(markets)
                except Exception as e:
                    logger.error(f"Failed to fetch market for slug '{slug}': {e}")

            logger.info(f"\n{'='*70}")
            logger.info(f"📊 Found {len(all_markets)} active market(s)")
            logger.info(f"{'='*70}")

            for i, market in enumerate(all_markets, 1):
                days_until = market.days_until_target()
                logger.info(f"\nMarket #{i}:")
                logger.info(f"  Question: {market.question}")
                logger.info(f"  Market ID: {market.market_id}")
                logger.info(f"  Target Date: {market.target_date.date()} (J-{days_until})")
                logger.info(f"  Outcomes: {len(market.outcomes)} temperature ranges")
                logger.info(f"  Volume 24h: ${market.volume_24h:,.2f}")
                logger.info(f"  Status: {'🔴 Resolved' if market.resolved else '🟢 Active'}")

                # Show outcome prices
                logger.info(f"  Prices:")
                for outcome in market.outcomes[:3]:  # Show first 3
                    logger.info(f"    • {outcome.temperature_range.label}: ${outcome.price:.3f}")
                if len(market.outcomes) > 3:
                    logger.info(f"    ... and {len(market.outcomes) - 3} more outcomes")

            return all_markets

        except Exception as e:
            logger.error(f"Failed to scan markets: {e}")
            return []

    def get_forecast_for_market(
        self,
        market: TemperatureMarket
    ) -> Optional[WeatherForecast]:
        """
        Get weather forecast for a market's target date.

        Args:
            market: Temperature market

        Returns:
            Weather forecast or None
        """
        try:
            forecasts = self.weather_client.get_forecast_with_confidence(days=7)

            # Find forecast matching market's target date
            target_date = market.target_date.date()

            for forecast in forecasts:
                if forecast.date.date() == target_date:
                    logger.debug(
                        f"Forecast for {target_date}: {forecast.max_temperature}°F "
                        f"(confidence: {forecast.confidence:.2f})"
                    )
                    return forecast

            logger.warning(f"No forecast found for {target_date}")
            return None

        except Exception as e:
            logger.error(f"Failed to get forecast: {e}")
            return None

    def determine_market_state(
        self,
        market: TemperatureMarket
    ) -> BotState:
        """
        Determine appropriate state for a market.

        Args:
            market: Temperature market

        Returns:
            Appropriate bot state
        """
        days_until = market.days_until_target()

        if market.is_target_day():
            return BotState.DAY_OF_MONITORING

        if 1 <= days_until <= self.settings.advance_days:
            # Within trading window
            if self.settings.enable_market_making:
                return BotState.MARKET_MAKING
            else:
                return BotState.POSITIONING

        if days_until < 0:
            # Past target date
            return BotState.WAITING_RESOLUTION

        # Too far in future
        return BotState.SCANNING

    def handle_positioning(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> None:
        """
        Handle position taking for a market.

        Args:
            market: Temperature market
            forecast: Weather forecast
        """
        if not self.position_taker:
            return

        try:
            logger.info(f"\n   🔍 Analyzing market opportunities...")

            # Analyze market and potentially place order
            order = self.position_taker.analyze_market(market, forecast)

            if order:
                logger.info(f"   ✅ Edge found! Placing order:")
                logger.info(f"      • Outcome: {order.outcome_id[:12]}...")
                logger.info(f"      • Side: {order.side.value}")
                logger.info(f"      • Price: ${order.price:.4f}")
                logger.info(f"      • Size: ${order.size:.2f}")

                # Add market_id to order
                order.market_id = market.market_id

                # Execute order
                if self.position_taker.execute_order(order):
                    logger.info(f"   🎉 Position successfully taken!")
                    logger.info(f"      Order ID: {order.outcome_id[:20]}...")
                else:
                    logger.warning(f"   ❌ Failed to execute order")
            else:
                logger.info(f"   ℹ️  No edge detected - market prices align with forecast")
                logger.info(f"      This is normal and healthy! Waiting for better opportunity.")

            # Update positions
            self.position_taker.update_positions()

        except Exception as e:
            logger.error(f"   ❌ Error in positioning: {e}")

    def handle_market_making(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> None:
        """
        Handle market making for a market.

        Args:
            market: Temperature market
            forecast: Weather forecast
        """
        if not self.market_maker:
            return

        # Market making runs in its own loop
        # We just start it in a separate thread
        if market.market_id not in self.monitors:
            logger.info(f"Starting market making for {market.market_id[:8]}...")

            # Run in separate thread
            thread = Thread(
                target=self.market_maker.run_market_making_loop,
                args=(market, forecast),
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
            self.monitors[market.market_id] = thread

    def handle_day_of_monitoring(
        self,
        market: TemperatureMarket
    ) -> None:
        """
        Handle real-time monitoring on target day.

        Args:
            market: Temperature market
        """
        logger.info(f"\n   🔴 REAL-TIME MONITORING MODE")
        logger.info(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"   📅 Today is the target day!")
        logger.info(f"   🔄 Will check temperature every 1 second")
        logger.info(f"   🎯 Will adjust positions if temperature changes range")
        logger.info(f"   ⏰ Monitoring until end of day (23:00)")
        logger.info(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        # Create monitor if not exists
        if market.market_id not in self.monitors:
            monitor = RealtimeMonitor(
                weather_client=self.weather_client,
                check_interval=self.settings.historical_check_interval_seconds
            )
            self.monitors[market.market_id] = monitor

            # Create adjuster
            strategy = self.position_taker or self.market_maker
            if strategy:
                adjuster = PositionAdjuster(
                    strategy=strategy,
                    market=market
                )

                # Define callback
                def on_temp_change(old_max: float, new_max: float):
                    logger.warning(
                        f"Temperature changed: {old_max}°F -> {new_max}°F"
                    )
                    adjuster.adjust_for_temperature(old_max, new_max)

                # Start monitoring in separate thread
                thread = Thread(
                    target=monitor.monitor_until_end_of_day,
                    args=(market, on_temp_change),
                    daemon=True
                )
                thread.start()
                self.threads.append(thread)

    def run_main_loop(self) -> None:
        """Run the main trading loop."""
        logger.info("Starting main trading loop")
        self.running = True
        self.state = BotState.SCANNING

        iteration = 0

        try:
            while self.running and not self.shutdown_event.is_set():
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"Iteration #{iteration} | State: {self.state.value}")
                logger.info(f"{'='*60}")

                try:
                    # Scan for markets
                    markets = self.scan_markets()

                    if not markets:
                        logger.info("No markets found, waiting...")
                        time.sleep(self.settings.check_interval_seconds)
                        continue

                    # Process each market
                    logger.info(f"\n{'='*70}")
                    logger.info(f"🔄 Processing {len(markets)} market(s)")
                    logger.info(f"{'='*70}\n")

                    for idx, market in enumerate(markets, 1):
                        logger.info(f"\n{'─'*70}")
                        logger.info(f"📈 Market {idx}/{len(markets)}: {market.question[:60]}...")
                        logger.info(f"   ID: {market.market_id}")
                        logger.info(f"   Target: {market.target_date.date()} (J-{market.days_until_target()})")
                        logger.info(f"{'─'*70}")

                        # Get forecast
                        logger.info(f"☁️  Fetching weather forecast for {market.target_date.date()}...")
                        forecast = self.get_forecast_for_market(market)

                        if not forecast:
                            logger.warning(f"⚠️  No forecast available, skipping this market")
                            continue

                        logger.info(
                            f"✅ Forecast: {forecast.max_temp}°F "
                            f"(confidence: {forecast.confidence:.0%})"
                        )

                        # Determine market state
                        market_state = self.determine_market_state(market)
                        self.market_states[market.market_id] = market_state

                        # State emoji mapping
                        state_emojis = {
                            BotState.POSITIONING: "💼",
                            BotState.MARKET_MAKING: "📊",
                            BotState.DAY_OF_MONITORING: "🔴",
                            BotState.WAITING_RESOLUTION: "⏳",
                            BotState.SCANNING: "🔍"
                        }

                        emoji = state_emojis.get(market_state, "❓")
                        logger.info(f"{emoji} State: {market_state.value}")

                        # Handle based on state
                        if market_state == BotState.POSITIONING:
                            logger.info(f"🎯 Analyzing for position taking...")
                            self.handle_positioning(market, forecast)

                        elif market_state == BotState.MARKET_MAKING:
                            logger.info(f"📊 Running market making strategy...")
                            self.handle_market_making(market, forecast)

                        elif market_state == BotState.DAY_OF_MONITORING:
                            logger.info(f"🔴 LIVE: Starting real-time monitoring (target day is TODAY)")
                            self.handle_day_of_monitoring(market)

                        elif market_state == BotState.WAITING_RESOLUTION:
                            logger.info(f"⏳ Market ended, waiting for resolution...")
                            logger.info(f"   Will check back later")

                    # Wait before next iteration
                    logger.info(
                        f"\nSleeping for {self.settings.check_interval_seconds}s..."
                    )
                    time.sleep(self.settings.check_interval_seconds)

                except Exception as e:
                    logger.error(f"Error in iteration: {e}", exc_info=True)
                    time.sleep(30)  # Wait longer on error

        except KeyboardInterrupt:
            logger.info("\nShutdown signal received")

        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Shutdown bot gracefully."""
        logger.info("Shutting down bot...")
        self.running = False
        self.shutdown_event.set()
        self.state = BotState.STOPPED

        # Stop all strategies
        if self.market_maker:
            self.market_maker.stopped = True
            self.market_maker.cancel_all_orders()

        if self.position_taker:
            # Could close all positions here if desired
            pass

        # Stop all monitors
        for monitor in self.monitors.values():
            if hasattr(monitor, 'stop_monitoring'):
                monitor.stop_monitoring()

        # Wait for threads to finish
        logger.info("Waiting for threads to finish...")
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)

        logger.info("Bot shutdown complete")

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"\nReceived signal {signum}")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def run(self) -> None:
        """Run the bot."""
        self.setup_signal_handlers()

        logger.info("\n" + "="*60)
        logger.info("🤖 Poly-Weather Trading Bot Started")
        logger.info("="*60)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE TRADING'}")
        logger.info(f"Position Taking: {'✓' if self.position_taker else '✗'}")
        logger.info(f"Market Making: {'✓' if self.market_maker else '✗'}")
        logger.info("="*60 + "\n")

        # Run main loop
        self.run_main_loop()
