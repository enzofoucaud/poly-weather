"""
Configuration settings for the Polymarket trading bot.
Uses Pydantic for validation and type checking.
"""

from typing import Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main configuration class for the trading bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ============================================
    # POLYMARKET CONFIGURATION
    # ============================================
    polymarket_private_key: str = Field(
        ...,
        description="Private key for signing transactions"
    )
    polymarket_proxy_address: Optional[str] = Field(
        default=None,
        description="Proxy address for Polymarket (optional)"
    )
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com",
        description="Polygon RPC endpoint"
    )
    chain_id: int = Field(
        default=137,
        description="Chain ID (137=Mainnet, 80001=Mumbai Testnet)"
    )

    # ============================================
    # WEATHER.COM API CONFIGURATION
    # ============================================
    weather_api_key: str = Field(
        ...,
        description="Weather.com API key"
    )
    weather_geocode: str = Field(
        default="40.761,-73.864",
        description="NYC LaGuardia coordinates (lat,lon)"
    )
    weather_location_id: str = Field(
        default="KLGA:9:US",
        description="Location ID for historical data"
    )

    # ============================================
    # TRADING CONFIGURATION
    # ============================================
    max_position_size: float = Field(
        default=100.0,
        gt=0,
        description="Maximum position size per trade (USDC)"
    )
    min_spread: float = Field(
        default=0.02,
        ge=0,
        le=1,
        description="Minimum spread for market making (0.02 = 2%)"
    )
    max_slippage: float = Field(
        default=0.05,
        ge=0,
        le=1,
        description="Maximum acceptable slippage (0.05 = 5%)"
    )
    advance_days: int = Field(
        default=3,
        ge=1,
        le=7,
        description="Days in advance to start trading"
    )

    # ============================================
    # RISK MANAGEMENT
    # ============================================
    max_daily_loss: float = Field(
        default=50.0,
        gt=0,
        description="Maximum daily loss before stopping (USDC)"
    )
    max_exposure_per_market: float = Field(
        default=200.0,
        gt=0,
        description="Maximum total exposure per market (USDC)"
    )
    max_market_making_inventory: float = Field(
        default=500.0,
        gt=0,
        description="Maximum inventory for market making (shares)"
    )

    # ============================================
    # BOT BEHAVIOR
    # ============================================
    check_interval_seconds: int = Field(
        default=60,
        ge=1,
        description="How often to check for updates (seconds)"
    )
    historical_check_interval_seconds: int = Field(
        default=1,
        ge=1,
        description="How often to check historical data on target day (seconds)"
    )
    enable_market_making: bool = Field(
        default=False,
        description="Enable market making strategy"
    )
    enable_position_taking: bool = Field(
        default=True,
        description="Enable position taking strategy"
    )

    # ============================================
    # DRY RUN (PAPER TRADING)
    # ============================================
    dry_run_mode: bool = Field(
        default=True,
        description="Enable dry run mode (simulation)"
    )
    dry_run_initial_balance: float = Field(
        default=1000.0,
        gt=0,
        description="Initial balance for dry run (USDC)"
    )
    dry_run_transaction_fee: float = Field(
        default=0.002,
        ge=0,
        le=1,
        description="Simulated transaction fee (0.002 = 0.2%)"
    )

    # ============================================
    # LOGGING
    # ============================================
    log_level: str = Field(
        default="INFO",
        description="Log level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_to_file: bool = Field(
        default=True,
        description="Enable file logging"
    )
    log_rotation: str = Field(
        default="daily",
        description="Log file rotation (daily, weekly, or size in MB)"
    )
    log_retention_days: int = Field(
        default=30,
        ge=1,
        description="Keep logs for N days"
    )

    # ============================================
    # DATABASE
    # ============================================
    database_path: str = Field(
        default="data/trading.db",
        description="Database file path"
    )

    # ============================================
    # MONITORING & ALERTS
    # ============================================
    enable_alerts: bool = Field(
        default=False,
        description="Enable alerts"
    )
    alert_email: Optional[str] = Field(
        default=None,
        description="Alert email address"
    )
    alert_webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for alerts (Discord/Slack)"
    )

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is one of the accepted values."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()

    @validator("polymarket_private_key")
    def validate_private_key(cls, v, values):
        """Validate private key format."""
        # Allow dummy key in dry-run mode
        dry_run = values.get('dry_run_mode', True)
        if dry_run and (not v or v == "0x" + "0" * 64):
            # Return dummy key for dry-run
            return "0x" + "0" * 64

        if not v:
            raise ValueError(
                "polymarket_private_key must be set. "
                "Please update your .env file."
            )

        if not v.startswith("0x"):
            v = "0x" + v
        if len(v) != 66:  # 0x + 64 hex chars
            raise ValueError("polymarket_private_key must be 64 hex characters (with or without 0x prefix)")
        return v

    @validator("weather_geocode")
    def validate_geocode(cls, v):
        """Validate geocode format (lat,lon)."""
        parts = v.split(",")
        if len(parts) != 2:
            raise ValueError("weather_geocode must be in format 'lat,lon'")
        try:
            lat, lon = float(parts[0]), float(parts[1])
            if not (-90 <= lat <= 90):
                raise ValueError("Latitude must be between -90 and 90")
            if not (-180 <= lon <= 180):
                raise ValueError("Longitude must be between -180 and 180")
        except ValueError as e:
            raise ValueError(f"Invalid geocode format: {e}")
        return v

    def is_production(self) -> bool:
        """Check if running in production mode (real money)."""
        return not self.dry_run_mode

    def get_weather_api_url(self, endpoint: str) -> str:
        """Get the full Weather.com API URL for a given endpoint."""
        base_url = "https://api.weather.com"
        return f"{base_url}/{endpoint}"


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create the global settings instance.
    This function ensures settings are loaded only once.
    """
    global settings
    if settings is None:
        settings = Settings()
    return settings


def reload_settings() -> Settings:
    """
    Reload settings from environment.
    Useful for testing or if .env file changes.
    """
    global settings
    settings = Settings()
    return settings
