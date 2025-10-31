"""
Polymarket CLOB API client for trading temperature markets.
"""

from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType as ClobOrderType
from py_clob_client.constants import POLYGON

from ..utils.logger import get_logger
from ..models.market import TemperatureMarket, PolymarketOutcome, TemperatureRange
from ..models.trade import Order, Position, Trade, OrderSide, OrderType, OrderStatus

logger = get_logger()


class PolymarketClient:
    """Client for interacting with Polymarket CLOB API."""

    def __init__(
        self,
        private_key: str,
        chain_id: int = 137,
        proxy_address: Optional[str] = None,
        dry_run: bool = True
    ):
        """
        Initialize Polymarket client.

        Args:
            private_key: Private key for signing transactions
            chain_id: Chain ID (137=Polygon Mainnet, 80001=Mumbai Testnet)
            proxy_address: Optional proxy address
            dry_run: If True, simulate trades without executing
        """
        self.private_key = private_key
        self.chain_id = chain_id
        self.proxy_address = proxy_address
        self.dry_run = dry_run

        # Initialize CLOB client
        try:
            host = "https://clob.polymarket.com" if chain_id == 137 else "https://clob-testnet.polymarket.com"

            self.client = ClobClient(
                host=host,
                key=private_key,
                chain_id=chain_id,
                signature_type=2,  # EIP712
                funder=proxy_address
            )

            # Get wallet address
            self.address = self.client.get_address()

            logger.info(
                f"PolymarketClient initialized | "
                f"Address: {self.address} | "
                f"Chain: {chain_id} | "
                f"Dry Run: {dry_run}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Polymarket client: {e}")
            raise

    def get_balance(self) -> float:
        """
        Get USDC balance.

        Returns:
            USDC balance as float
        """
        if self.dry_run:
            logger.debug("Dry run mode: returning simulated balance")
            return 1000.0

        try:
            # Get allowance info which includes balance
            allowances = self.client.get_allowances()
            balance = float(allowances.get("balance", 0)) / 1e6  # Convert from wei

            logger.debug(f"USDC balance: {balance:.2f}")
            return balance

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0

    def setup_allowances(self, amount: Optional[float] = None) -> bool:
        """
        Setup USDC allowances for trading.

        Args:
            amount: Amount to approve (None = unlimited)

        Returns:
            True if successful
        """
        if self.dry_run:
            logger.info("Dry run mode: skipping allowance setup")
            return True

        try:
            logger.info(f"Setting up allowances for {amount if amount else 'unlimited'} USDC")

            # Approve the exchange contract to spend USDC
            # The py-clob-client handles this internally when needed
            # but we can check current allowances
            allowances = self.client.get_allowances()
            current_allowance = float(allowances.get("allowance", 0)) / 1e6

            logger.info(f"Current allowance: {current_allowance:.2f} USDC")

            if amount and current_allowance < amount:
                logger.warning(
                    f"Current allowance ({current_allowance:.2f}) is less than "
                    f"requested ({amount:.2f}). You may need to approve more."
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to setup allowances: {e}")
            return False

    def get_temperature_markets(
        self,
        city: str = "NYC",
        active_only: bool = True
    ) -> List[TemperatureMarket]:
        """
        Get all temperature markets for a city.

        Args:
            city: City name (e.g., "NYC", "New York")
            active_only: Only return active (unresolved) markets

        Returns:
            List of TemperatureMarket objects
        """
        try:
            logger.info(f"Fetching temperature markets for {city}")

            # Search for markets containing temperature keywords
            # Note: The actual API endpoint may vary
            # This is a simplified implementation
            markets_data = self._search_markets(f"temperature {city}")

            markets = []
            for market_data in markets_data:
                try:
                    market = self._parse_market(market_data)

                    if active_only and market.resolved:
                        continue

                    markets.append(market)

                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            logger.info(f"Found {len(markets)} temperature markets")
            return markets

        except Exception as e:
            logger.error(f"Failed to get temperature markets: {e}")
            return []

    def _search_markets(self, query: str) -> List[Dict]:
        """
        Search for markets by query using Gamma API.

        Args:
            query: Search query

        Returns:
            List of market data dictionaries
        """
        try:
            import requests

            # Use Polymarket's Gamma API (public markets endpoint)
            url = "https://gamma-api.polymarket.com/markets"

            params = {
                "limit": 100,
                "archived": "false",
                "closed": "false"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            all_markets = response.json()

            logger.debug(f"Fetched {len(all_markets)} markets from Gamma API")

            # Filter by query (case-insensitive)
            filtered = [
                m for m in all_markets
                if query.lower() in m.get("question", "").lower()
            ]

            logger.info(f"Found {len(filtered)} markets matching '{query}'")
            return filtered

        except Exception as e:
            logger.error(f"Market search failed: {e}")
            return []

    def _parse_market(self, market_data: Dict) -> TemperatureMarket:
        """
        Parse market data into TemperatureMarket object.

        Args:
            market_data: Raw market data from Gamma API

        Returns:
            TemperatureMarket object
        """
        # Extract basic info from Gamma API response
        market_id = market_data.get("conditionId", "")
        question = market_data.get("question", "")

        # Parse target date from question
        # Example: "Highest temperature in NYC on October 30?"
        target_date = self._parse_target_date_from_question(question)

        # Parse outcomes from the outcomes array
        outcomes = []
        outcomes_data = market_data.get("outcomes", [])

        for i, outcome_text in enumerate(outcomes_data):
            outcome = self._parse_outcome(market_data, outcome_text, i)
            if outcome:
                outcomes.append(outcome)

        # Create market object
        market = TemperatureMarket(
            market_id=market_id,
            question=question,
            target_date=target_date,
            outcomes=outcomes,
            volume_24h=float(market_data.get("volume24hr", 0)),
            liquidity=float(market_data.get("liquidity", 0)),
            resolved=market_data.get("closed", False)
        )

        return market

    def _parse_outcome(self, market_data: Dict, outcome_text: str, index: int) -> Optional[PolymarketOutcome]:
        """
        Parse outcome data from Gamma API.

        Args:
            market_data: Full market data containing token info
            outcome_text: Outcome label (e.g., "61-62°F")
            index: Index of this outcome in the outcomes array

        Returns:
            PolymarketOutcome object or None
        """
        try:
            # Get token ID from outcomePrices array
            outcome_prices = market_data.get("outcomePrices", [])
            token_id = f"{market_data.get('conditionId', '')}_{index}"

            # Get price for this outcome
            price = 0.5  # Default
            if index < len(outcome_prices):
                try:
                    price = float(outcome_prices[index])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid price for outcome {index}: {outcome_prices[index]}")

            # Parse temperature range from outcome text
            temp_range = TemperatureRange.from_label(outcome_text)

            # Get tokens data if available
            tokens = market_data.get("tokens", [])
            if index < len(tokens):
                token_info = tokens[index]
                token_id = token_info.get("token_id", token_id)

            outcome = PolymarketOutcome(
                token_id=token_id,
                price=price,
                temperature_range=temp_range,
                liquidity=0.0,  # Not available in basic API response
                volume_24h=0.0
            )

            return outcome

        except Exception as e:
            logger.warning(f"Failed to parse outcome '{outcome_text}': {e}")
            return None

    def _parse_target_date_from_question(self, question: str) -> datetime:
        """
        Parse target date from market question.

        Args:
            question: Market question text

        Returns:
            Target datetime
        """
        import re
        from dateutil import parser as date_parser

        try:
            # Look for date patterns like "October 30", "Oct 30, 2025", etc.
            # This is a simplified parser - you may need more robust parsing

            # Try to find month and day
            month_day_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})'

            match = re.search(month_day_pattern, question, re.IGNORECASE)

            if match:
                date_str = match.group(0)
                # Add current year if not specified
                current_year = datetime.now().year
                parsed_date = date_parser.parse(f"{date_str} {current_year}")

                # If the date is in the past, assume next year
                if parsed_date < datetime.now():
                    parsed_date = date_parser.parse(f"{date_str} {current_year + 1}")

                return parsed_date

            # Fallback: return tomorrow
            logger.warning(f"Could not parse date from question: {question}")
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        except Exception as e:
            logger.error(f"Date parsing failed: {e}")
            return datetime.now()

    def get_market_orderbook(
        self,
        token_id: str,
        side: Optional[str] = None
    ) -> Dict:
        """
        Get orderbook for a specific token/outcome.

        Args:
            token_id: Token identifier
            side: Optional side filter ("BUY" or "SELL")

        Returns:
            Orderbook data with bids and asks
        """
        try:
            orderbook = self.client.get_order_book(token_id)

            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])

            # Calculate best bid/ask
            best_bid = float(bids[0]["price"]) if bids else None
            best_ask = float(asks[0]["price"]) if asks else None

            spread = (best_ask - best_bid) if best_bid and best_ask else None

            return {
                "bids": bids,
                "asks": asks,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": spread
            }

        except Exception as e:
            logger.error(f"Failed to get orderbook for {token_id}: {e}")
            return {"bids": [], "asks": [], "best_bid": None, "best_ask": None, "spread": None}

    def place_order(self, order: Order) -> str:
        """
        Place an order on Polymarket.

        Args:
            order: Order object to place

        Returns:
            Order ID
        """
        if self.dry_run:
            import uuid
            order_id = f"dry_run_{uuid.uuid4().hex[:8]}"
            logger.info(
                f"[DRY RUN] Order placed: {order.side.value} {order.size:.2f} "
                f"@ {order.price:.4f} | ID: {order_id}"
            )
            return order_id

        try:
            # Prepare order args
            order_args = OrderArgs(
                token_id=order.outcome_id,
                price=order.price,
                size=order.size,
                side=order.side.value,
                order_type=ClobOrderType.GTC  # Good til cancelled
            )

            # Submit order
            result = self.client.create_order(order_args)
            order_id = result.get("orderID", "")

            logger.info(
                f"Order placed: {order.side.value} {order.size:.2f} @ {order.price:.4f} | "
                f"ID: {order_id}"
            )

            from ..utils.logger import log_trade
            log_trade(
                action=order.side.value,
                market_id=order.market_id,
                outcome_id=order.outcome_id,
                price=order.price,
                size=order.size,
                details={"order_id": order_id, "dry_run": False}
            )

            return order_id

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if successful
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Order cancelled: {order_id}")
            return True

        try:
            self.client.cancel_order(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_order_status(self, order_id: str) -> OrderStatus:
        """
        Get order status.

        Args:
            order_id: Order ID

        Returns:
            OrderStatus enum
        """
        if self.dry_run:
            return OrderStatus.FILLED

        try:
            order = self.client.get_order(order_id)
            status_str = order.get("status", "").upper()

            status_map = {
                "LIVE": OrderStatus.PENDING,
                "MATCHED": OrderStatus.FILLED,
                "PARTIAL": OrderStatus.PARTIALLY_FILLED,
                "CANCELLED": OrderStatus.CANCELLED
            }

            return status_map.get(status_str, OrderStatus.PENDING)

        except Exception as e:
            logger.error(f"Failed to get order status for {order_id}: {e}")
            return OrderStatus.FAILED

    def get_positions(self) -> List[Position]:
        """
        Get all open positions.

        Returns:
            List of Position objects
        """
        if self.dry_run:
            logger.debug("[DRY RUN] No positions in dry run mode")
            return []

        try:
            # Get user's positions from the API
            # This implementation depends on available endpoints
            positions_data = self.client.get_positions()

            positions = []
            for pos_data in positions_data:
                position = self._parse_position(pos_data)
                if position:
                    positions.append(position)

            logger.info(f"Retrieved {len(positions)} open positions")
            return positions

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def _parse_position(self, pos_data: Dict) -> Optional[Position]:
        """Parse position data into Position object."""
        try:
            position = Position(
                market_id=pos_data.get("market_id", ""),
                outcome_id=pos_data.get("token_id", ""),
                shares=float(pos_data.get("size", 0)),
                avg_entry_price=float(pos_data.get("avg_price", 0)),
                current_price=float(pos_data.get("current_price", 0))
            )
            return position

        except Exception as e:
            logger.warning(f"Failed to parse position: {e}")
            return None

    def close_position(
        self,
        position: Position,
        price: Optional[float] = None
    ) -> bool:
        """
        Close a position by selling all shares.

        Args:
            position: Position to close
            price: Limit price (None for market order)

        Returns:
            True if successful
        """
        try:
            # Create sell order for all shares
            order = Order(
                market_id=position.market_id,
                outcome_id=position.outcome_id,
                side=OrderSide.SELL,
                size=position.shares,
                price=price if price else position.current_price,
                order_type=OrderType.MARKET if price is None else OrderType.LIMIT
            )

            order_id = self.place_order(order)

            logger.info(f"Position close order placed: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return False
