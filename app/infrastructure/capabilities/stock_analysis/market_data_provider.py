from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from decimal import Decimal

from app.domain.stock_analysis import StockSymbol, PriceBar, FundamentalMetrics


@dataclass(frozen=True)
class MarketDataRequest:
    symbols: tuple[StockSymbol, ...]
    start_date: date
    end_date: date


class MarketDataProvider(Protocol):
    """Provider for fetching market data."""

    def fetch_price_history(self, request: MarketDataRequest) -> dict[StockSymbol, list[PriceBar]]:
        """Fetch OHLCV price bars for symbols in date range."""
        ...

    def fetch_fundamentals(self, symbols: tuple[StockSymbol, ...], as_of: date) -> dict[StockSymbol, FundamentalMetrics]:
        """Fetch fundamental metrics for symbols as of a date."""
        ...


class YFinanceMarketDataProvider:
    """Yahoo Finance market data provider using yfinance library."""

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    def fetch_price_history(self, request: MarketDataRequest) -> dict[StockSymbol, list[PriceBar]]:
        import yfinance as yf

        result: dict[StockSymbol, list[PriceBar]] = {}
        for symbol in request.symbols:
            try:
                ticker = yf.Ticker(str(symbol))
                hist = ticker.history(
                    start=request.start_date,
                    end=request.end_date,
                    auto_adjust=False,
                    timeout=self._timeout,
                )
                if hist.empty:
                    result[symbol] = []
                    continue

                bars: list[PriceBar] = []
                for idx, row in hist.iterrows():
                    bar = PriceBar.create(
                        symbol=symbol,
                        session_date=idx.date(),
                        open=Decimal(str(row["Open"])),
                        high=Decimal(str(row["High"])),
                        low=Decimal(str(row["Low"])),
                        close=Decimal(str(row["Close"])),
                        volume=int(row["Volume"]),
                        adjusted_close=Decimal(str(row["Adj Close"])) if "Adj Close" in row else None,
                    )
                    bars.append(bar)
                result[symbol] = bars
            except Exception:
                result[symbol] = []
        return result

    def fetch_fundamentals(self, symbols: tuple[StockSymbol, ...], as_of: date) -> dict[StockSymbol, FundamentalMetrics]:
        import yfinance as yf

        result: dict[StockSymbol, FundamentalMetrics] = {}
        for symbol in symbols:
            try:
                ticker = yf.Ticker(str(symbol))
                info = ticker.info

                def get_decimal(key: str) -> Decimal | None:
                    value = info.get(key)
                    if value is None:
                        return None
                    try:
                        return Decimal(str(value))
                    except Exception:
                        return None

                metrics = FundamentalMetrics.create(
                    symbol=symbol,
                    as_of=as_of,
                    pe_ratio=get_decimal("trailingPE"),
                    pb_ratio=get_decimal("priceToBook"),
                    roe=get_decimal("returnOnEquity"),
                    debt_to_equity=get_decimal("debtToEquity"),
                    earnings_growth_qoq=get_decimal("earningsQuarterlyGrowth"),
                    earnings_growth_yoy=None,
                    revenue_growth_qoq=get_decimal("revenueQuarterlyGrowth"),
                    revenue_growth_yoy=None,
                    profit_margin=get_decimal("profitMargins"),
                    current_ratio=get_decimal("currentRatio"),
                    market_cap=get_decimal("marketCap"),
                )
                result[symbol] = metrics
            except Exception:
                result[symbol] = FundamentalMetrics.create(symbol=symbol, as_of=as_of)
        return result