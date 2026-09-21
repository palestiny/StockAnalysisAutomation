from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from app.application.capability import Capability
from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import PriceBar, StockSymbol, TechnicalIndicators
from app.infrastructure.capabilities.stock_analysis.market_data_acquire import (
    MarketDataAcquireResult,
)

TECHNICAL_ANALYSIS_CAPABILITY_ID = "technical_analysis"


class TechnicalAnalyzer(Protocol):
    """Protocol for technical analysis computations."""

    def compute_indicators(self, symbol: StockSymbol, bars: list[PriceBar], as_of: date) -> TechnicalIndicators:
        ...


class DefaultTechnicalAnalyzer:
    """Default implementation using pure Python (no external dependencies)."""

    def compute_indicators(self, symbol: StockSymbol, bars: list[PriceBar], as_of: date) -> TechnicalIndicators:
        if not bars:
            return TechnicalIndicators.create(symbol=symbol, as_of=as_of)

        closes = [bar.close for bar in bars]
        highs = [bar.high for bar in bars]
        lows = [bar.low for bar in bars]
        volumes = [Decimal(str(bar.volume)) for bar in bars]

        indicators = {}

        indicators["rsi_14"] = self._compute_rsi(closes, 14)
        macd_line, macd_signal, macd_hist = self._compute_macd(closes)
        indicators["macd_line"] = macd_line
        indicators["macd_signal"] = macd_signal
        indicators["macd_histogram"] = macd_hist
        indicators["sma_20"] = self._compute_sma(closes, 20)
        indicators["sma_50"] = self._compute_sma(closes, 50)
        indicators["ema_12"] = self._compute_ema(closes, 12)
        indicators["ema_26"] = self._compute_ema(closes, 26)
        bb_upper, bb_middle, bb_lower = self._compute_bollinger_bands(closes, 20)
        indicators["bb_upper"] = bb_upper
        indicators["bb_middle"] = bb_middle
        indicators["bb_lower"] = bb_lower
        indicators["atr_14"] = self._compute_atr(highs, lows, closes, 14)
        indicators["volume_sma_20"] = self._compute_sma(volumes, 20)

        return TechnicalIndicators.create(symbol=symbol, as_of=as_of, **indicators)

    def _compute_rsi(self, prices: list[Decimal], period: int) -> Decimal | None:
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(Decimal("0"))
            else:
                gains.append(Decimal("0"))
                losses.append(abs(change))

        avg_gain = sum(gains[:period]) / Decimal(str(period))
        avg_loss = sum(losses[:period]) / Decimal(str(period))

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * Decimal(str(period - 1)) + gains[i]) / Decimal(str(period))
            avg_loss = (avg_loss * Decimal(str(period - 1)) + losses[i]) / Decimal(str(period))

        if avg_loss == 0:
            return Decimal("100")
        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
        return rsi

    def _compute_macd(self, prices: list[Decimal]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        ema_12 = self._compute_ema(prices, 12)
        ema_26 = self._compute_ema(prices, 26)

        if ema_12 is None or ema_26 is None:
            return None, None, None

        macd_line = ema_12 - ema_26
        macd_signal = macd_line
        macd_histogram = macd_line - macd_signal

        return macd_line, macd_signal, macd_histogram

    def _compute_sma(self, values: list[Decimal], period: int) -> Decimal | None:
        if len(values) < period:
            return None
        return sum(values[-period:]) / Decimal(str(period))

    def _compute_ema(self, prices: list[Decimal], period: int) -> Decimal | None:
        if len(prices) < period:
            return None

        multiplier = Decimal("2") / Decimal(str(period + 1))
        ema = prices[0]
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _compute_bollinger_bands(self, prices: list[Decimal], period: int) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        if len(prices) < period:
            return None, None, None

        sma = self._compute_sma(prices, period)
        if sma is None:
            return None, None, None

        recent = prices[-period:]
        variance = sum((p - sma) ** 2 for p in recent) / Decimal(str(period))
        std_dev = Decimal(str(float(variance) ** 0.5))

        upper = sma + (Decimal("2") * std_dev)
        lower = sma - (Decimal("2") * std_dev)

        return upper, sma, lower

    def _compute_atr(self, highs: list[Decimal], lows: list[Decimal], closes: list[Decimal], period: int) -> Decimal | None:
        if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
            return None

        true_ranges = []
        for i in range(1, len(highs)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i - 1])
            tr3 = abs(lows[i] - closes[i - 1])
            true_ranges.append(max(tr1, tr2, tr3))

        if len(true_ranges) < period:
            return None

        atr = sum(true_ranges[-period:]) / Decimal(str(period))
        return atr


class TechnicalAnalysisCapability(Capability):
    """Capability to compute technical indicators from price history."""

    def __init__(self, analyzer: TechnicalAnalyzer | None = None) -> None:
        self._analyzer = analyzer or DefaultTechnicalAnalyzer()

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        try:
            market_data = context.get("market_data")
        except KeyError:
            return CapabilityResult.failure("market_data is required in execution context")

        if not isinstance(market_data, MarketDataAcquireResult):
            return CapabilityResult.failure("market_data must be a MarketDataAcquireResult")

        indicators: dict[StockSymbol, TechnicalIndicators] = {}
        for symbol, bars in market_data.price_history.items():
            if bars:
                indicators[symbol] = self._analyzer.compute_indicators(symbol, bars, market_data.as_of)

        context.set("technical_indicators", indicators)
        return CapabilityResult.success()
