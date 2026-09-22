from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Generic, TypeVar
from dataclasses import dataclass, asdict
from decimal import Decimal

from app.domain.stock_analysis import StockSymbol, PriceBar, FundamentalMetrics
from app.infrastructure.capabilities.stock_analysis.market_data_provider import MarketDataProvider, MarketDataRequest


T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    data: T
    timestamp: float
    ttl_seconds: int

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": self._serialize_data(self.data),
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], data_type: type[T]) -> "CacheEntry[T]":
        return cls(
            data=cls._deserialize_data(data["data"], data_type),
            timestamp=data["timestamp"],
            ttl_seconds=data["ttl_seconds"],
        )

    @staticmethod
    def _serialize_data(data: Any) -> Any:
        if isinstance(data, dict):
            return {str(k): CacheEntry._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [CacheEntry._serialize_data(v) for v in data]
        elif isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, StockSymbol):
            return str(data)
        elif isinstance(data, PriceBar):
            return {
                "symbol": str(data.symbol),
                "session_date": data.session_date.isoformat(),
                "open": str(data.open),
                "high": str(data.high),
                "low": str(data.low),
                "close": str(data.close),
                "volume": data.volume,
                "adjusted_close": str(data.adjusted_close) if data.adjusted_close else None,
            }
        elif isinstance(data, FundamentalMetrics):
            result = {
                "symbol": str(data.symbol),
                "as_of": data.as_of.isoformat(),
            }
            for field in ["pe_ratio", "pb_ratio", "roe", "debt_to_equity",
                          "earnings_growth_qoq", "earnings_growth_yoy",
                          "revenue_growth_qoq", "revenue_growth_yoy",
                          "profit_margin", "current_ratio", "market_cap"]:
                value = getattr(data, field)
                result[field] = str(value) if value is not None else ""  # type: ignore[assignment]
            return result
        return data

    @staticmethod
    def _deserialize_data(data: Any, data_type: type) -> Any:
        if data_type == dict[StockSymbol, list[PriceBar]]:
            price_result: dict[StockSymbol, list[PriceBar]] = {}
            for k, v in data.items():
                symbol = StockSymbol(k)
                bars = []
                for bar_data in v:
                    bars.append(PriceBar.create(
                        symbol=symbol,
                        session_date=date.fromisoformat(bar_data["session_date"]),
                        open=Decimal(bar_data["open"]),
                        high=Decimal(bar_data["high"]),
                        low=Decimal(bar_data["low"]),
                        close=Decimal(bar_data["close"]),
                        volume=bar_data["volume"],
                        adjusted_close=Decimal(bar_data["adjusted_close"]) if bar_data["adjusted_close"] else None,
                    ))
                price_result[symbol] = bars
            return price_result
        elif data_type == dict[StockSymbol, FundamentalMetrics]:
            fund_result: dict[StockSymbol, FundamentalMetrics] = {}
            for k, v in data.items():
                symbol = StockSymbol(k)
                metrics_data = {k2: Decimal(v2) if v2 is not None else None for k2, v2 in v.items() if k2 not in ("symbol", "as_of")}
                fund_result[symbol] = FundamentalMetrics.create(
                    symbol=symbol,
                    as_of=date.fromisoformat(v["as_of"]),
                    **metrics_data,
                )
            return fund_result
        return data


class FileCache:
    """File-based cache with TTL support."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or (Path.home() / ".automation_os" / "stock_analysis" / "cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, CacheEntry[Any]] = {}

    def _get_cache_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_")
        return self._cache_dir / f"{safe_key}.json"

    def get(self, key: str, data_type: type[T]) -> T | None:
        # Check memory first
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if not entry.is_expired():
                return entry.data  # type: ignore[no-any-return]
            else:
                del self._memory_cache[key]

        # Check file
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    cached_data = json.load(f)
                entry = CacheEntry.from_dict(cached_data, data_type)
                if not entry.is_expired():
                    self._memory_cache[key] = entry
                    return entry.data  # type: ignore[no-any-return]
                else:
                    cache_path.unlink(missing_ok=True)
            except Exception:
                cache_path.unlink(missing_ok=True)
        return None

    def set(self, key: str, data: T, ttl_seconds: int = 3600) -> None:
        entry = CacheEntry(data=data, timestamp=time.time(), ttl_seconds=ttl_seconds)
        self._memory_cache[key] = entry

        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "w") as f:
                json.dump(entry.to_dict(), f)
        except Exception:
            pass

    def clear(self) -> None:
        self._memory_cache.clear()
        for cache_file in self._cache_dir.glob("*.json"):
            cache_file.unlink(missing_ok=True)


class CachedMarketDataProvider(MarketDataProvider):
    """Market data provider with caching layer."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache: FileCache | None = None,
        price_history_ttl: int = 3600,  # 1 hour
        fundamentals_ttl: int = 86400,  # 24 hours
    ) -> None:
        self._provider = provider
        self._cache = cache or FileCache()
        self._price_history_ttl = price_history_ttl
        self._fundamentals_ttl = fundamentals_ttl

    def fetch_price_history(self, request: MarketDataRequest) -> dict[StockSymbol, list[PriceBar]]:
        cache_key = f"price_history_{'_'.join(str(s) for s in request.symbols)}_{request.start_date}_{request.end_date}"

        cached = self._cache.get(cache_key, dict[StockSymbol, list[PriceBar]])
        if cached is not None:
            return cached

        data = self._provider.fetch_price_history(request)
        self._cache.set(cache_key, data, self._price_history_ttl)
        return data

    def fetch_fundamentals(self, symbols: tuple[StockSymbol, ...], as_of: date) -> dict[StockSymbol, FundamentalMetrics]:
        cache_key = f"fundamentals_{'_'.join(str(s) for s in symbols)}_{as_of}"

        cached = self._cache.get(cache_key, dict[StockSymbol, FundamentalMetrics])
        if cached is not None:
            return cached

        data = self._provider.fetch_fundamentals(symbols, as_of)
        self._cache.set(cache_key, data, self._fundamentals_ttl)
        return data


def create_cached_market_data_provider(
    provider: MarketDataProvider | None = None,
    cache_dir: Path | None = None,
) -> CachedMarketDataProvider:
    from app.infrastructure.capabilities.stock_analysis.market_data_provider import YFinanceMarketDataProvider

    base_provider = provider or YFinanceMarketDataProvider()
    cache = FileCache(cache_dir)
    return CachedMarketDataProvider(base_provider, cache)