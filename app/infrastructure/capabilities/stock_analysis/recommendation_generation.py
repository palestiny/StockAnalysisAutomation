from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.application.capability import Capability
from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import (
    StockSymbol,
    TechnicalIndicators,
    MLScore,
    Recommendation,
    RecommendationAction,
    Watchlist,
)
from app.infrastructure.capabilities.stock_analysis.market_data_acquire import MarketDataAcquireResult
from app.infrastructure.capabilities.stock_analysis.fundamental_analysis import FundamentalScore


RECOMMENDATION_GENERATION_CAPABILITY_ID = "recommendation_generation"


@dataclass(frozen=True)
class ScoringWeights:
    technical: Decimal = Decimal("0.3")
    fundamental: Decimal = Decimal("0.3")
    ml: Decimal = Decimal("0.4")


class RecommendationGenerator(Protocol):
    """Protocol for generating recommendations from combined signals."""

    def generate(
        self,
        symbol: StockSymbol,
        watchlist_entry,
        market_data: MarketDataAcquireResult,
        technical: TechnicalIndicators | None,
        fundamental: FundamentalScore | None,
        ml: MLScore | None,
    ) -> Recommendation | None:
        ...


class DefaultRecommendationGenerator:
    """Default recommendation generator using weighted scoring."""

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self._weights = weights or ScoringWeights()

    def _compute_technical_score(self, indicators: TechnicalIndicators | None) -> Decimal | None:
        if not indicators:
            return None

        score = Decimal("0.5")

        if indicators.rsi_14 is not None:
            rsi = indicators.rsi_14
            if rsi < Decimal("30"):
                score += Decimal("0.2")
            elif rsi < Decimal("40"):
                score += Decimal("0.1")
            elif rsi > Decimal("70"):
                score -= Decimal("0.2")
            elif rsi > Decimal("60"):
                score -= Decimal("0.1")

        if indicators.macd_histogram is not None:
            if indicators.macd_histogram > Decimal("0"):
                score += Decimal("0.1")
            else:
                score -= Decimal("0.1")

        if indicators.ema_12 is not None and indicators.ema_26 is not None:
            if indicators.ema_12 > indicators.ema_26:
                score += Decimal("0.1")
            else:
                score -= Decimal("0.1")

        return max(Decimal("0"), min(Decimal("1"), score))

    def generate(
        self,
        symbol: StockSymbol,
        watchlist_entry,
        market_data: MarketDataAcquireResult,
        technical: TechnicalIndicators | None,
        fundamental: FundamentalScore | None,
        ml: MLScore | None,
    ) -> Recommendation | None:
        bars = market_data.price_history.get(symbol, [])
        if not bars:
            return None

        last_close = bars[-1].close

        tech_score = self._compute_technical_score(technical)
        fund_score = fundamental.score if fundamental else None
        ml_score = ml

        combined = Decimal("0")
        total_weight = Decimal("0")

        if tech_score is not None:
            combined += tech_score * self._weights.technical
            total_weight += self._weights.technical

        if fund_score is not None:
            combined += fund_score * self._weights.fundamental
            total_weight += self._weights.fundamental

        if ml_score is not None:
            combined += ml_score.probability_up * self._weights.ml
            total_weight += self._weights.ml

        if total_weight == 0:
            return None

        final_score = combined / total_weight

        min_confidence = watchlist_entry.min_confidence
        if final_score >= min_confidence:
            action = RecommendationAction.BUY
        elif final_score >= Decimal("0.4"):
            action = RecommendationAction.WATCH
        else:
            action = RecommendationAction.AVOID

        atr = technical.atr_14 if technical and technical.atr_14 else last_close * Decimal("0.02")
        entry = last_close
        stop_loss = entry - (atr * Decimal("2")) if action == RecommendationAction.BUY else None
        target = entry + (atr * Decimal("3")) if action == RecommendationAction.BUY else None

        rationale = []
        if tech_score is not None:
            rationale.append(f"Technical score: {tech_score:.2f}")
        if fund_score is not None:
            rationale.append(f"Fundamental score: {fund_score:.2f}")
        if ml_score is not None:
            rationale.append(f"ML probability: {ml_score.probability_up:.2f}")
        if fundamental and fundamental.factors:
            rationale.append(f"Fundamental factors: {', '.join(fundamental.factors)}")

        return Recommendation.create(
            symbol=symbol,
            action=action,
            confidence=final_score,
            rationale=rationale,
            entry_price=entry,
            stop_loss=stop_loss,
            target_price=target,
            technical_score=tech_score,
            fundamental_score=fund_score,
            ml_score=ml_score,
        )


class RecommendationGenerationCapability(Capability):
    """Capability to generate ranked recommendations from all signals."""

    def __init__(self, generator: RecommendationGenerator | None = None) -> None:
        self._generator = generator or DefaultRecommendationGenerator()

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        try:
            watchlist = context.get("watchlist")
            market_data = context.get("market_data")
            technical_indicators = context.get("technical_indicators")
            fundamental_scores = context.get("fundamental_scores")
            ml_scores = context.get("ml_scores")
        except KeyError as e:
            return CapabilityResult.failure(f"Missing required context: {e}")

        if not isinstance(watchlist, Watchlist):
            return CapabilityResult.failure("watchlist must be a Watchlist instance")
        if not isinstance(market_data, MarketDataAcquireResult):
            return CapabilityResult.failure("market_data must be a MarketDataAcquireResult")

        recommendations: list[Recommendation] = []
        for entry in watchlist.entries:
            if not entry.enabled:
                continue

            symbol = entry.symbol
            technical = technical_indicators.get(symbol) if technical_indicators else None
            fundamental = fundamental_scores.get(symbol) if fundamental_scores else None
            ml = ml_scores.get(symbol) if ml_scores else None

            rec = self._generator.generate(
                symbol=symbol,
                watchlist_entry=entry,
                market_data=market_data,
                technical=technical,
                fundamental=fundamental,
                ml=ml,
            )
            if rec:
                recommendations.append(rec)

        recommendations.sort(key=lambda r: r.confidence, reverse=True)

        context.set("recommendations", recommendations)
        return CapabilityResult.success()