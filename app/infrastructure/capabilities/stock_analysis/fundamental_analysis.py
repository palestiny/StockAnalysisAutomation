from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.application.capability import Capability
from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import FundamentalMetrics, StockSymbol
from app.infrastructure.capabilities.stock_analysis.market_data_acquire import (
    MarketDataAcquireResult,
)

FUNDAMENTAL_ANALYSIS_CAPABILITY_ID = "fundamental_analysis"


@dataclass(frozen=True)
class FundamentalScore:
    symbol: StockSymbol
    score: Decimal
    factors: tuple[str, ...]


class FundamentalAnalyzer(Protocol):
    """Protocol for fundamental analysis scoring."""

    def score_fundamentals(self, symbol: StockSymbol, metrics: FundamentalMetrics) -> FundamentalScore:
        ...


class DefaultFundamentalAnalyzer:
    """Default fundamental scoring based on value/growth/quality factors."""

    def score_fundamentals(self, symbol: StockSymbol, metrics: FundamentalMetrics) -> FundamentalScore:
        factors: list[str] = []
        score = Decimal("0.5")

        if metrics.pe_ratio is not None:
            if metrics.pe_ratio < Decimal("15"):
                score += Decimal("0.1")
                factors.append("low_pe")
            elif metrics.pe_ratio > Decimal("30"):
                score -= Decimal("0.1")
                factors.append("high_pe")

        if metrics.pb_ratio is not None:
            if metrics.pb_ratio < Decimal("1.5"):
                score += Decimal("0.05")
                factors.append("low_pb")
            elif metrics.pb_ratio > Decimal("5"):
                score -= Decimal("0.05")
                factors.append("high_pb")

        if metrics.roe is not None:
            if metrics.roe > Decimal("0.15"):
                score += Decimal("0.1")
                factors.append("high_roe")
            elif metrics.roe < Decimal("0.05"):
                score -= Decimal("0.1")
                factors.append("low_roe")

        if metrics.debt_to_equity is not None:
            if metrics.debt_to_equity < Decimal("0.5"):
                score += Decimal("0.05")
                factors.append("low_debt")
            elif metrics.debt_to_equity > Decimal("2"):
                score -= Decimal("0.1")
                factors.append("high_debt")

        if metrics.profit_margin is not None:
            if metrics.profit_margin > Decimal("0.15"):
                score += Decimal("0.05")
                factors.append("high_margin")
            elif metrics.profit_margin < Decimal("0.05"):
                score -= Decimal("0.05")
                factors.append("low_margin")

        if metrics.current_ratio is not None:
            if metrics.current_ratio > Decimal("1.5"):
                score += Decimal("0.03")
                factors.append("strong_liquidity")
            elif metrics.current_ratio < Decimal("1"):
                score -= Decimal("0.05")
                factors.append("weak_liquidity")

        if metrics.earnings_growth_qoq is not None:
            if metrics.earnings_growth_qoq > Decimal("0.1"):
                score += Decimal("0.1")
                factors.append("strong_earnings_growth")
            elif metrics.earnings_growth_qoq < Decimal("-0.1"):
                score -= Decimal("0.1")
                factors.append("declining_earnings")

        if metrics.revenue_growth_qoq is not None:
            if metrics.revenue_growth_qoq > Decimal("0.1"):
                score += Decimal("0.05")
                factors.append("strong_revenue_growth")

        score = max(Decimal("0"), min(Decimal("1"), score))

        return FundamentalScore(symbol=symbol, score=score, factors=tuple(factors))


class FundamentalAnalysisCapability(Capability):
    """Capability to score fundamentals for each symbol."""

    def __init__(self, analyzer: FundamentalAnalyzer | None = None) -> None:
        self._analyzer = analyzer or DefaultFundamentalAnalyzer()

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        try:
            market_data = context.get("market_data")
        except KeyError:
            return CapabilityResult.failure("market_data is required in execution context")

        if not isinstance(market_data, MarketDataAcquireResult):
            return CapabilityResult.failure("market_data must be a MarketDataAcquireResult")

        scores: dict[StockSymbol, FundamentalScore] = {}
        for symbol, metrics in market_data.fundamentals.items():
            scores[symbol] = self._analyzer.score_fundamentals(symbol, metrics)

        context.set("fundamental_scores", scores)
        return CapabilityResult.success()
