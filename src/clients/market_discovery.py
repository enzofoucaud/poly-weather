"""
Automatic market discovery for Polymarket temperature markets.
Scans for available markets without requiring manual event slugs.
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from ..utils.logger import get_logger

logger = get_logger()


class MarketDiscovery:
    """Automatically discovers temperature markets on Polymarket."""

    def __init__(self, city: str = "NYC"):
        """
        Initialize market discovery.

        Args:
            city: Target city for temperature markets
        """
        self.city = city
        self.base_url = "https://gamma-api.polymarket.com"

    def discover_temperature_events(
        self,
        days_ahead: int = 7,
        active_only: bool = True
    ) -> List[Dict]:
        """
        Discover all temperature market events for the next N days.

        Args:
            days_ahead: Number of days ahead to search
            active_only: Only return active (non-closed) events

        Returns:
            List of event data dictionaries with event slugs
        """
        logger.info(f"Discovering temperature markets for {self.city} (next {days_ahead} days)")

        try:
            # Try two approaches:
            # 1. Search through events
            # 2. Search through individual markets

            temperature_events = []

            # Approach 1: Search events
            logger.debug("Searching through events...")
            url = f"{self.base_url}/events"
            params = {
                "limit": 500,  # Increased limit
                "archived": "false"
            }

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            all_events = response.json()

            logger.debug(f"Fetched {len(all_events)} total events")

            # Filter for temperature events in our city
            temperature_events = []
            city_keywords = self._get_city_keywords()

            for event in all_events:
                title = event.get("title", "").lower()
                slug = event.get("slug", "")

                # Check if it's a temperature market for our city
                if not self._is_temperature_market(title, city_keywords):
                    continue

                # Check if event is active if required
                if active_only and event.get("closed", False):
                    continue

                # Parse target date from title or endDate
                target_date = self._parse_event_date(event)
                if not target_date:
                    continue

                # Check if within our time window
                days_until = (target_date.date() - datetime.now().date()).days
                if 0 <= days_until <= days_ahead:
                    event_info = {
                        "slug": slug,
                        "title": event.get("title"),
                        "target_date": target_date,
                        "days_until": days_until,
                        "active": not event.get("closed", False),
                        "volume_24h": event.get("volume24hr", 0),
                        "markets_count": len(event.get("markets", []))
                    }
                    temperature_events.append(event_info)

            # Sort by target date
            temperature_events.sort(key=lambda x: x["target_date"])

            # If no events found through scanning, try direct slug generation
            if not temperature_events:
                logger.info("No events found through API scan, trying direct slug generation...")
                temperature_events = self._try_direct_slugs(days_ahead)

            logger.info(f"Found {len(temperature_events)} temperature event(s)")
            for evt in temperature_events:
                logger.info(
                    f"  - {evt['title']} | "
                    f"Target: {evt['target_date'].date()} (J-{evt['days_until']}) | "
                    f"Slug: {evt['slug']}"
                )

            return temperature_events

        except Exception as e:
            logger.error(f"Failed to discover markets: {e}")
            return []

    def _try_direct_slugs(self, days_ahead: int) -> List[Dict]:
        """
        Try to access markets using predictable slug patterns.

        Args:
            days_ahead: Number of days to check

        Returns:
            List of found events
        """
        logger.debug("Attempting direct slug generation for temperature markets")

        found_events = []
        city_slug = self.city.lower().replace(" ", "-")

        # Try each day
        for days in range(days_ahead + 1):
            target_date = datetime.now() + timedelta(days=days)

            # Generate possible slug patterns
            month_name = target_date.strftime("%B").lower()
            day = target_date.day

            # Pattern: "highest-temperature-in-{city}-on-{month}-{day}"
            slug = f"highest-temperature-in-{city_slug}-on-{month_name}-{day}"

            # Try to fetch this event
            try:
                url = f"{self.base_url}/events"
                params = {"slug": slug}

                response = requests.get(url, params=params, timeout=5)
                if response.status_code == 200:
                    events = response.json()

                    if events and len(events) > 0:
                        event = events[0]

                        event_info = {
                            "slug": slug,
                            "title": event.get("title", f"Temperature in {self.city} on {month_name} {day}"),
                            "target_date": target_date.replace(hour=12, minute=0, second=0, microsecond=0),
                            "days_until": days,
                            "active": not event.get("closed", False),
                            "volume_24h": event.get("volume24hr", 0),
                            "markets_count": len(event.get("markets", []))
                        }

                        found_events.append(event_info)
                        logger.info(f"✓ Found event via direct slug: {slug}")

            except Exception as e:
                logger.debug(f"Slug {slug} not found: {e}")
                continue

        return found_events

    def _get_city_keywords(self) -> List[str]:
        """Get search keywords for the city."""
        city_map = {
            "NYC": ["new york", "nyc", "new york city"],
            "LA": ["los angeles", "la"],
            "Chicago": ["chicago"],
            "Miami": ["miami"],
            "Boston": ["boston"],
        }
        return city_map.get(self.city, [self.city.lower()])

    def _is_temperature_market(self, title: str, city_keywords: List[str]) -> bool:
        """
        Check if title indicates a temperature market for our city.

        Args:
            title: Event title (lowercase)
            city_keywords: Keywords for city

        Returns:
            True if it's a temperature market for our city
        """
        # Must contain temperature keywords
        temp_keywords = ["temperature", "temp", "degrees", "°f", "fahrenheit"]
        has_temp = any(kw in title for kw in temp_keywords)

        if not has_temp:
            return False

        # Must contain city keywords
        has_city = any(kw in title for kw in city_keywords)

        return has_city

    def _parse_event_date(self, event: Dict) -> Optional[datetime]:
        """
        Parse target date from event data.

        Args:
            event: Event data dictionary

        Returns:
            Target datetime or None
        """
        # Try endDate first
        end_date_str = event.get("endDate", "")
        if end_date_str:
            try:
                return datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except Exception:
                pass

        # Try parsing from title
        title = event.get("title", "")
        return self._parse_date_from_title(title)

    def _parse_date_from_title(self, title: str) -> Optional[datetime]:
        """
        Parse date from event title.

        Args:
            title: Event title like "Highest temperature in NYC on October 31?"

        Returns:
            Parsed datetime or None
        """
        import re
        from dateutil import parser as date_parser

        try:
            # Look for month and day patterns
            month_day_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})'

            match = re.search(month_day_pattern, title, re.IGNORECASE)

            if match:
                date_str = match.group(0)
                current_year = datetime.now().year

                # Try current year first
                parsed_date = date_parser.parse(f"{date_str} {current_year}")

                # If date is in the past, try next year
                if parsed_date.date() < datetime.now().date():
                    parsed_date = date_parser.parse(f"{date_str} {current_year + 1}")

                return parsed_date

        except Exception as e:
            logger.warning(f"Failed to parse date from title '{title}': {e}")

        return None

    def get_event_slugs_for_next_days(
        self,
        days_ahead: int = 3
    ) -> List[str]:
        """
        Get event slugs for the next N days.

        Args:
            days_ahead: Number of days ahead to include

        Returns:
            List of event slugs
        """
        events = self.discover_temperature_events(days_ahead=days_ahead, active_only=True)
        return [evt["slug"] for evt in events]
