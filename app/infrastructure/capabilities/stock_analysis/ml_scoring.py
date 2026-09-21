from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Protocol

from app.application.capability import Capability
from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import StockSymbol, TechnicalIndicators, MLScore
from app.infrastructure.capabilities.stock_analysis.market_data_acquire import MarketDataAcquireResult
from app.infrastructure.capabilities.stock_analysis.fundamental_analysis import FundamentalScore


ML_SCORING_CAPABILITY_ID = "ml_scoring"

MODEL_VERSION = "v1.0.0-mock"


class MLModelProvider(Protocol):
    """Protocol for ML model inference."""

    def predict(self, features: dict[str, float]) -> float:
        """Return probability of next-session positive return (0-1)."""
        ...


class MockMLModelProvider:
    """Mock ML model for testing - replaces with real model in production."""

    def predict(self, features: dict[str, float]) -> float:
        score = 0.5

        rsi = features.get("rsi_14", 50)
        if rsi < 30:
            score += 0.15
        elif rsi > 70:
            score -= 0.1
        elif 40 <= rsi <= 60:
            score += 0.05

        macd_hist = features.get("macd_histogram", 0)
        if macd_hist > 0:
            score += 0.05
        elif macd_hist < 0:
            score -= 0.05

        price_vs_sma20 = features.get("price_vs_sma20", 0)
        if price_vs_sma20 > 0.02:
            score += 0.05
        elif price_vs_sma20 < -0.02:
            score -= 0.05

        volume_ratio = features.get("volume_ratio", 1)
        if volume_ratio > 1.5:
            score += 0.03

        fund_score = features.get("fundamental_score", 0.5)
        score += (fund_score - 0.5) * 0.3

        return max(0.0, min(1.0, score))


class MLScoringCapability(Capability):
    """Capability to score symbols using ML model."""

    def __init__(
        self,
        model_provider: MLModelProvider | None = None,
        model_version: str = MODEL_VERSION,
    ) -> None:
        self._model = model_provider or MockMLModelProvider()
        self._model_version = model_version

    def _extract_features(
        self,
        symbol: StockSymbol,
        indicators: TechnicalIndicators | None,
        fundamental_score: FundamentalScore | None,
        price_history: list,
    ) -> dict[str, float]:
        features = {}

        if indicators:
            features["rsi_14"] = float(indicators.rsi_14) if indicators.rsi_14 else 50.0
            features["macd_histogram"] = float(indicators.macd_histogram) if indicators.macd_histogram else 0.0
            features["macd_line"] = float(indicators.macd_line) if indicators.macd_line else 0.0

            if indicators.sma_20 and price_history:
                last_close = float(price_history[-1].close)
                sma_20 = float(indicators.sma_20)
                features["price_vs_sma20"] = (last_close - sma_20) / sma_20 if sma_20 != 0 else 0.0

            if indicators.volume_sma_20 and price_history:
                last_volume = float(price_history[-1].volume)
                vol_sma = float(indicators.volume_sma_20)
                features["volume_ratio"] = last_volume / vol_sma if vol_sma != 0 else 1.0

        if fundamental_score:
            features["fundamental_score"] = float(fundamental_score.score)

        return features

    def _compute_features_hash(self, features: dict[str, float]) -> str:
        serialized = json.dumps(features, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        try:
            market_data = context.get("market_data")
            technical_indicators = context.get("technical_indicators")
            fundamental_scores = context.get("fundamental_scores")
        except KeyError as e:
            return CapabilityResult.failure(f"Missing required context: {e}")

        if not isinstance(market_data, MarketDataAcquireResult):
            return CapabilityResult.failure("market_data must be a MarketDataAcquireResult")

        ml_scores: dict[StockSymbol, MLScore] = {}
        for symbol in market_data.price_history:
            indicators = technical_indicators.get(symbol) if technical_indicators else None
            fund_score = fundamental_scores.get(symbol) if fundamental_scores else None
            bars = market_data.price_history.get(symbol, [])

            features = self._extract_features(symbol, indicators, fund_score, bars)
            probability = self._model.predict(features)
            features_hash = self._compute_features_hash(features)

            ml_scores[symbol] = MLScore.create(
                symbol=symbol,
                as_of=market_data.as_of,
                probability_up=Decimal(str(probability)),
                model_version=self._model_version,
                features_hash=features_hash,
            )

        context.set("ml_scores", ml_scores)
        return CapabilityResult.success()