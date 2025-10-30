#!/usr/bin/env python3
"""
Main entry point for the Poly-Weather trading bot.
"""

import click
from src.bot import TradingBot
from src.utils.logger import get_logger

logger = get_logger()


@click.group()
def cli():
    """Poly-Weather Trading Bot - Trade temperature markets on Polymarket."""
    pass


@cli.command()
@click.option(
    '--dry-run/--live',
    default=True,
    help='Run in dry-run mode (simulation) or live trading mode'
)
@click.option(
    '--duration',
    type=int,
    default=None,
    help='Run for N seconds then stop (for testing)'
)
def run(dry_run: bool, duration: int):
    """
    Run the trading bot.

    Examples:
        python main.py run --dry-run
        python main.py run --live
        python main.py run --dry-run --duration 300  # Run for 5 minutes
    """
    if not dry_run:
        click.confirm(
            '⚠️  WARNING: You are about to run in LIVE mode with REAL money. '
            'Are you sure?',
            abort=True
        )

    click.echo("=" * 60)
    click.echo(f"🤖 Starting Poly-Weather Trading Bot")
    click.echo(f"Mode: {'DRY RUN (Simulation)' if dry_run else 'LIVE TRADING'}")
    if duration:
        click.echo(f"Duration: {duration} seconds")
    click.echo("=" * 60)

    # Create and run bot
    bot = TradingBot(dry_run=dry_run)

    if duration:
        # Run for limited time (useful for testing)
        import threading
        timer = threading.Timer(duration, bot.shutdown)
        timer.start()

    try:
        bot.run()
    except KeyboardInterrupt:
        click.echo("\n\nShutting down...")
        bot.shutdown()
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        logger.error(f"Fatal error: {e}", exc_info=True)
        bot.shutdown()
        raise


@cli.command()
@click.option(
    '--days',
    type=int,
    default=7,
    help='Number of days to simulate'
)
@click.option(
    '--initial-balance',
    type=float,
    default=1000.0,
    help='Initial balance in USDC'
)
def simulate(days: int, initial_balance: float):
    """
    Run a multi-day simulation (dry-run).

    This will simulate trading over multiple days using historical or
    forecasted data.

    Examples:
        python main.py simulate --days 7
        python main.py simulate --days 30 --initial-balance 5000
    """
    click.echo(f"📊 Running {days}-day simulation with ${initial_balance} initial balance")
    click.echo("This feature is not yet implemented.")
    click.echo("Please use 'python main.py run --dry-run' for now.")


@cli.command()
def status():
    """
    Check bot status and configuration.
    """
    from src.config.settings import get_settings

    settings = get_settings()

    click.echo("=" * 60)
    click.echo("📊 Bot Configuration Status")
    click.echo("=" * 60)

    click.echo("\n🌤️  Weather API:")
    click.echo(f"  API Key: {'✓ Set' if settings.weather_api_key else '✗ Not set'}")
    click.echo(f"  Location: {settings.weather_geocode}")

    click.echo("\n💰 Polymarket:")
    click.echo(f"  Private Key: {'✓ Set' if settings.polymarket_private_key else '✗ Not set'}")
    click.echo(f"  Chain ID: {settings.chain_id}")

    click.echo("\n📈 Trading Config:")
    click.echo(f"  Max Position Size: ${settings.max_position_size}")
    click.echo(f"  Max Daily Loss: ${settings.max_daily_loss}")
    click.echo(f"  Min Spread: {settings.min_spread * 100}%")

    click.echo("\n🎯 Strategies:")
    click.echo(f"  Position Taking: {'✓ Enabled' if settings.enable_position_taking else '✗ Disabled'}")
    click.echo(f"  Market Making: {'✓ Enabled' if settings.enable_market_making else '✗ Disabled'}")

    click.echo("\n🔧 Bot Behavior:")
    click.echo(f"  Check Interval: {settings.check_interval_seconds}s")
    click.echo(f"  Advance Days: {settings.advance_days}")

    click.echo("\n💵 Dry Run:")
    click.echo(f"  Mode: {'✓ Enabled' if settings.dry_run_mode else '✗ Disabled (LIVE)'}")
    click.echo(f"  Initial Balance: ${settings.dry_run_initial_balance}")

    click.echo("\n" + "=" * 60)


@cli.command()
def test():
    """
    Run test suite.
    """
    import subprocess
    import sys

    click.echo("🧪 Running test suite...")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        env={"PYTHONPATH": "."}
    )

    sys.exit(result.returncode)


@cli.command()
@click.argument('key')
@click.argument('value')
def config(key: str, value: str):
    """
    Update configuration values in .env file.

    Examples:
        python main.py config MAX_POSITION_SIZE 200
        python main.py config ENABLE_MARKET_MAKING true
    """
    click.echo(f"Setting {key} = {value}")
    click.echo("This feature is not yet implemented.")
    click.echo("Please edit .env file manually.")


if __name__ == '__main__':
    cli()
