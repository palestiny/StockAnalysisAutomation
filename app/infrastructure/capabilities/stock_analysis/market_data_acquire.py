from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol

from app.application.capability import Capability
from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import StockSymbol, PriceBar, FundamentalMetrics, Watchlist
from app.infrastructure.capabilities.stock_analysis.market_data_provider import MarketDataProvider, MarketDataRequest, YFinanceMarketDataProvider


MARKET_DATA_ACQUIRE_CAPABILITY_ID = "market_data_acquire"


@dataclass(frozen=True)
class MarketDataAcquireResult:
    price_history: dict[StockSymbol, list[PriceBar]]
    fundamentals: dict[StockSymbol, FundamentalMetrics]
    as_of: date


class MarketDataAcquireCapability(Capability):
    """Capability to acquire market data for a watchlist."""

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        lookback_days: int = 252,
    ) -> None:
        self._provider = provider or YFinanceMarketDataProvider()
        self._lookback_days = lookback_days

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        try:
            watchlist = context.get("watchlist")
        except KeyError:
            return CapabilityResult.failure("watchlist is required in execution context")

        if not isinstance(watchlist, Watchlist):
            return CapabilityResult.failure("watchlist must be a Watchlist instance")

        symbols = watchlist.enabled_symbols()
        if not symbols:
            return CapabilityResult.failure("no enabled symbols in watchlist")

        end_date = date.today()
        start_date = end_date - timedelta(days=self._lookback_days)

        request = MarketDataRequest(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

        price_history = self._provider.fetch_price_history(request)
        fundamentals = self._provider.fetch_fundamentals(symbols, end_date)

        result = MarketDataAcquireResult(
            price_history=price_history,
            fundamentals=fundamentals,
            as_of=end_date,
        )
        context.set("market_data", result)

        return CapabilityResult.success()