"""Tests for technical analysis capability."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import (
    PriceBar,
    StockSymbol,
)
from app.infrastructure.capabilities.stock_analysis.market_data_acquire import (
    MarketDataAcquireResult,
)
from app.infrastructure.capabilities.stock_analysis.technical_analysis import (
    DefaultTechnicalAnalyzer,
    TechnicalAnalysisCapability,
)


class TestDefaultTechnicalAnalyzer:
    def setup_method(self):
        self.analyzer = DefaultTechnicalAnalyzer()
        self.symbol = StockSymbol("AAPL")
        self.as_of = date(2024, 1, 15)

    def create_sample_bars(self, count: int = 30) -> list[PriceBar]:
        """Create sample price bars for testing."""
        bars = []
        base_price = Decimal("150.00")
        for i in range(count):
            # Simple trending price with some volatility
            price = base_price + Decimal(str(i * 0.5))
            bars.append(PriceBar.create(
                symbol=self.symbol,
                session_date=date(2024, 1, 1) + __import__('datetime').timedelta(days=i),
                open=price - Decimal("0.5"),
                high=price + Decimal("1.0"),
                low=price - Decimal("1.0"),
                close=price,
                volume=1000000 + i * 10000,
            ))
        return bars

    def test_compute_rsi_with_sufficient_data(self):
        bars = self.create_sample_bars(20)
        indicators = self.analyzer.compute_indicators(self.symbol, bars, self.as_of)
        assert indicators.rsi_14 is not None
        assert Decimal("0") <= indicators.rsi_14 <= Decimal("100")

    def test_compute_rsi_with_insufficient_data(self):
        bars = self.create_sample_bars(5)  # Less than 14 periods
        indicators = self.analyzer.compute_indicators(self.symbol, bars, self.as_of)
        assert indicators.rsi_14 is None

    def test_compute_sma(self):
        bars = self.create_sample_bars(25)
        indicators = self.analyzer.compute_indicators(self.symbol, bars, self.as_of)
        assert indicators.sma_20 is not None
        assert indicators.sma_50 is None  # Not enough data for 50

    def test_compute_ema(self):
        bars = self.create_sample_bars(15)
        indicators = self.analyzer.compute_indicators(self.symbol, bars, self.as_of)
        assert indicators.ema_12 is not None
        assert indicators.ema_26 is None  # Not enough data for 26

    def test_compute_macd(self):
        bars = self.create_sample_bars(30)
        indicators = self.analyzer.compute_indicators(self.symbol, bars, self.as_of)
        assert indicators.macd_line is not None
        assert indicators.macd_signal is not None
        assert indicators.macd_histogram is not None

    def test_compute_bollinger_bands(self):
        bars = self.create_sample_bars(25)
        indicators = self.analyzer.compute_indicators(self.symbol, bars, self.as_of)
        assert indicators.bb_upper is not None
        assert indicators.bb_middle is not None
        assert indicators.bb_lower is not None
        assert indicators.bb_upper > indicators.bb_middle > indicators.bb_lower

    def test_compute_atr(self):
        bars = self.create_sample_bars(20)
        indicators = self.analyzer.compute_indicators(self.symbol, bars, self.as_of)
        assert indicators.atr_14 is not None
        assert indicators.atr_14 > Decimal("0")

    def test_compute_volume_sma(self):
        bars = self.create_sample_bars(25)
        indicators = self.analyzer.compute_indicators(self.symbol, bars, self.as_of)
        assert indicators.volume_sma_20 is not None

    def test_empty_bars_returns_none_indicators(self):
        indicators = self.analyzer.compute_indicators(self.symbol, [], self.as_of)
        assert indicators.rsi_14 is None
        assert indicators.sma_20 is None


class TestTechnicalAnalysisCapability:
    def setup_method(self):
        self.analyzer = DefaultTechnicalAnalyzer()
        self.capability = TechnicalAnalysisCapability(analyzer=self.analyzer)

    def test_execute_with_market_data(self):
        symbol = StockSymbol("AAPL")
        as_of = date(2024, 1, 15)
        bars = [
            PriceBar.create(
                symbol=symbol,
                session_date=as_of - __import__('datetime').timedelta(days=i),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("149.00"),
                close=Decimal("153.00"),
                volume=1000000,
            )
            for i in range(25)
        ]

        market_data = MarketDataAcquireResult(
            price_history={symbol: bars},
            fundamentals={},
            as_of=as_of,
        )

        context = ExecutionContext()
        context.set("market_data", market_data)

        result = self.capability.execute(context)
        assert result.succeeded is True

        indicators = context.get("technical_indicators")
        assert symbol in indicators
        assert indicators[symbol].rsi_14 is not None

    def test_execute_without_market_data_fails(self):
        context = ExecutionContext()
        result = self.capability.execute(context)
        assert result.succeeded is False
        assert "market_data" in str(result.error).lower()
