"""Tests for fundamental analysis capability."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import (
    FundamentalMetrics,
    StockSymbol,
)
from app.infrastructure.capabilities.stock_analysis.fundamental_analysis import (
    DefaultFundamentalAnalyzer,
    FundamentalAnalysisCapability,
)
from app.infrastructure.capabilities.stock_analysis.market_data_acquire import (
    MarketDataAcquireResult,
)


class TestDefaultFundamentalAnalyzer:
    def setup_method(self):
        self.analyzer = DefaultFundamentalAnalyzer()
        self.symbol = StockSymbol("AAPL")
        self.as_of = date(2024, 1, 15)

    def test_low_pe_increases_score(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            pe_ratio=Decimal("10.0"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score > Decimal("0.5")
        assert "low_pe" in score.factors

    def test_high_pe_decreases_score(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            pe_ratio=Decimal("40.0"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score < Decimal("0.5")
        assert "high_pe" in score.factors

    def test_high_roe_increases_score(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            roe=Decimal("0.25"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score > Decimal("0.5")
        assert "high_roe" in score.factors

    def test_low_roe_decreases_score(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            roe=Decimal("0.03"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score < Decimal("0.5")
        assert "low_roe" in score.factors

    def test_low_debt_increases_score(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            debt_to_equity=Decimal("0.3"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score > Decimal("0.5")
        assert "low_debt" in score.factors

    def test_high_debt_decreases_score(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            debt_to_equity=Decimal("3.0"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score < Decimal("0.5")
        assert "high_debt" in score.factors

    def test_strong_earnings_growth_increases_score(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            earnings_growth_qoq=Decimal("0.2"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score > Decimal("0.5")
        assert "strong_earnings_growth" in score.factors

    def test_declining_earnings_decreases_score(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            earnings_growth_qoq=Decimal("-0.2"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score < Decimal("0.5")
        assert "declining_earnings" in score.factors

    def test_score_clamped_between_0_and_1(self):
        # Create metrics that would push score very high
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
            pe_ratio=Decimal("5.0"),
            roe=Decimal("0.5"),
            debt_to_equity=Decimal("0.1"),
            profit_margin=Decimal("0.3"),
            earnings_growth_qoq=Decimal("0.5"),
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score <= Decimal("1.0")
        assert score.score >= Decimal("0.0")

    def test_no_metrics_returns_neutral(self):
        metrics = FundamentalMetrics.create(
            symbol=self.symbol,
            as_of=self.as_of,
        )
        score = self.analyzer.score_fundamentals(self.symbol, metrics)
        assert score.score == Decimal("0.5")
        assert len(score.factors) == 0


class TestFundamentalAnalysisCapability:
    def setup_method(self):
        self.analyzer = DefaultFundamentalAnalyzer()
        self.capability = FundamentalAnalysisCapability(analyzer=self.analyzer)

    def test_execute_with_market_data(self):
        symbol = StockSymbol("AAPL")
        as_of = date(2024, 1, 15)
        metrics = FundamentalMetrics.create(
            symbol=symbol,
            as_of=as_of,
            pe_ratio=Decimal("15.0"),
            roe=Decimal("0.2"),
        )

        market_data = MarketDataAcquireResult(
            price_history={},
            fundamentals={symbol: metrics},
            as_of=as_of,
        )

        context = ExecutionContext()
        context.set("market_data", market_data)

        result = self.capability.execute(context)
        assert result.succeeded is True

        scores = context.get("fundamental_scores")
        assert symbol in scores
        assert scores[symbol].score > Decimal("0.5")

    def test_execute_without_market_data_fails(self):
        context = ExecutionContext()
        result = self.capability.execute(context)
        assert result.succeeded is False
