"""
Weather.com API client for fetching forecasts and historical data.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..utils.logger import get_logger
from ..models.market import WeatherForecast

logger = get_logger()


@dataclass
class HistoricalObservation:
    """Represents a single historical weather observation."""
    timestamp: datetime
    temperature: float
    location: str


class WeatherClient:
    """Client for interacting with Weather.com API."""

    BASE_URL = "https://api.weather.com"

    def __init__(
        self,
        api_key: str,
        geocode: str = "40.761,-73.864",
        location_id: str = "KLGA:9:US",
        timeout: int = 10
    ):
        """
        Initialize Weather.com client.

        Args:
            api_key: Weather.com API key
            geocode: Location coordinates (lat,lon)
            location_id: Location ID for historical data
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.geocode = geocode
        self.location_id = location_id
        self.timeout = timeout

        # Cache for forecast data
        self._forecast_cache: Optional[Dict] = None
        self._forecast_cache_time: Optional[datetime] = None
        self._forecast_cache_ttl = 300  # 5 minutes

        logger.info(f"WeatherClient initialized for location {location_id}")

    def _make_request(self, url: str, params: Dict) -> Dict:
        """
        Make HTTP request with error handling and retries.

        Args:
            url: Full URL to request
            params: Query parameters

        Returns:
            JSON response as dict

        Raises:
            requests.RequestException: If request fails after retries
        """
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise

            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                raise

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise

    def get_forecast(self, days: int = 7) -> Dict[datetime, float]:
        """
        Get temperature forecast for the next N days.

        Args:
            days: Number of days to forecast (max 7)

        Returns:
            Dictionary mapping date to max temperature in Fahrenheit
            Example: {datetime(2025, 10, 30): 62.0, datetime(2025, 10, 31): 63.0}
        """
        # Check cache
        if self._forecast_cache and self._forecast_cache_time:
            age = (datetime.now() - self._forecast_cache_time).total_seconds()
            if age < self._forecast_cache_ttl:
                logger.debug("Using cached forecast data")
                return self._parse_forecast(self._forecast_cache, days)

        logger.info(f"Fetching {days}-day forecast for {self.geocode}")

        url = f"{self.BASE_URL}/v3/wx/forecast/daily/7day"
        params = {
            "apiKey": self.api_key,
            "geocode": self.geocode,
            "language": "en-US",
            "units": "e",  # English units (Fahrenheit)
            "format": "json"
        }

        try:
            data = self._make_request(url, params)

            # Update cache
            self._forecast_cache = data
            self._forecast_cache_time = datetime.now()

            return self._parse_forecast(data, days)

        except Exception as e:
            logger.error(f"Failed to fetch forecast: {e}")
            raise

    def _parse_forecast(self, data: Dict, days: int) -> Dict[datetime, float]:
        """
        Parse forecast response and extract max temperatures.

        Args:
            data: Raw API response
            days: Number of days to extract

        Returns:
            Dictionary mapping date to max temperature
        """
        try:
            # Extract calendarDayTemperatureMax array
            max_temps = data.get("calendarDayTemperatureMax", [])

            if not max_temps:
                logger.error("No calendarDayTemperatureMax found in response")
                return {}

            # Map temperatures to dates
            result = {}
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            for i, temp in enumerate(max_temps[:days]):
                if temp is not None:
                    forecast_date = today + timedelta(days=i)
                    result[forecast_date] = float(temp)
                    logger.debug(f"Forecast for {forecast_date.date()}: {temp}°F")
                else:
                    logger.warning(f"Missing temperature data for day {i}")

            logger.info(f"Parsed forecast for {len(result)} days")
            return result

        except Exception as e:
            logger.error(f"Failed to parse forecast data: {e}")
            return {}

    def get_historical_today(self) -> Dict:
        """
        Get historical observations for today.
        Called frequently (every second) on target day to track max temperature.

        Returns:
            Dictionary with:
                - current_max: Maximum temperature observed so far today
                - observation_count: Number of observations
                - latest_temp: Most recent temperature reading
                - observations: List of all observations
        """
        today_str = datetime.now().strftime("%Y%m%d")

        logger.debug(f"Fetching historical data for {today_str}")

        url = f"{self.BASE_URL}/v1/location/{self.location_id}/observations/historical.json"
        params = {
            "apiKey": self.api_key,
            "units": "e",  # English units (Fahrenheit)
            "startDate": today_str
        }

        try:
            data = self._make_request(url, params)
            return self._parse_historical(data)

        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            raise

    def _parse_historical(self, data: Dict) -> Dict:
        """
        Parse historical observations and calculate current max.

        Args:
            data: Raw API response

        Returns:
            Dictionary with current_max, observation_count, latest_temp, observations
        """
        try:
            observations = data.get("observations", [])

            if not observations:
                logger.warning("No observations found in historical data")
                return {
                    "current_max": None,
                    "observation_count": 0,
                    "latest_temp": None,
                    "observations": []
                }

            # Extract all temperature readings
            temps = []
            for obs in observations:
                temp = obs.get("temp")
                if temp is not None:
                    temps.append(float(temp))

            if not temps:
                logger.warning("No valid temperature readings in observations")
                return {
                    "current_max": None,
                    "observation_count": len(observations),
                    "latest_temp": None,
                    "observations": observations
                }

            current_max = max(temps)
            latest_temp = temps[-1] if temps else None

            logger.debug(
                f"Historical data: {len(observations)} observations, "
                f"current max: {current_max}°F, latest: {latest_temp}°F"
            )

            return {
                "current_max": current_max,
                "observation_count": len(observations),
                "latest_temp": latest_temp,
                "observations": observations
            }

        except Exception as e:
            logger.error(f"Failed to parse historical data: {e}")
            return {
                "current_max": None,
                "observation_count": 0,
                "latest_temp": None,
                "observations": []
            }

    def get_forecast_with_confidence(self, days: int = 7) -> List[WeatherForecast]:
        """
        Get forecast with confidence scores based on how far ahead.

        Args:
            days: Number of days to forecast

        Returns:
            List of WeatherForecast objects with confidence scores
        """
        forecast_dict = self.get_forecast(days)

        forecasts = []
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for date, max_temp in forecast_dict.items():
            date_normalized = date.replace(hour=0, minute=0, second=0, microsecond=0)
            days_ahead = (date_normalized - now).days

            # Calculate confidence: higher for near-term forecasts
            # J-0: 0.95, J-1: 0.85, J-2: 0.75, J-3: 0.65, etc.
            confidence = max(0.5, 0.95 - (days_ahead * 0.10))

            forecast = WeatherForecast(
                date=date,
                max_temperature=max_temp,
                confidence=confidence,
                source="weather.com"
            )
            forecasts.append(forecast)

        return forecasts

    def detect_forecast_change(
        self,
        old_forecast: Dict[datetime, float],
        new_forecast: Dict[datetime, float],
        threshold: float = 1.0
    ) -> List[tuple[datetime, float, float]]:
        """
        Detect significant changes in forecast.

        Args:
            old_forecast: Previous forecast dict
            new_forecast: New forecast dict
            threshold: Minimum temperature change to be considered significant (°F)

        Returns:
            List of (date, old_temp, new_temp) tuples for significant changes
        """
        changes = []

        for date in new_forecast:
            if date in old_forecast:
                old_temp = old_forecast[date]
                new_temp = new_forecast[date]

                change = abs(new_temp - old_temp)
                if change >= threshold:
                    changes.append((date, old_temp, new_temp))
                    logger.info(
                        f"Forecast change detected for {date.date()}: "
                        f"{old_temp}°F → {new_temp}°F (Δ{new_temp - old_temp:+.1f}°F)"
                    )

        return changes

    def clear_cache(self) -> None:
        """Clear the forecast cache."""
        self._forecast_cache = None
        self._forecast_cache_time = None
        logger.debug("Forecast cache cleared")
