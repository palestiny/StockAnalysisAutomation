"""Tests for recommendation generation capability."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import (
    MLScore,
    PriceBar,
    RecommendationAction,
    StockSymbol,
    TechnicalIndicators,
    Watchlist,
    WatchlistEntry,
)
from app.infrastructure.capabilities.stock_analysis.fundamental_analysis import FundamentalScore
from app.infrastructure.capabilities.stock_analysis.market_data_acquire import (
    MarketDataAcquireResult,
)
from app.infrastructure.capabilities.stock_analysis.recommendation_generation import (
    DefaultRecommendationGenerator,
    RecommendationGenerationCapability,
    ScoringWeights,
)


class TestDefaultRecommendationGenerator:
    def setup_method(self):
        self.generator = DefaultRecommendationGenerator()
        self.symbol = StockSymbol("AAPL")
        self.as_of = date(2024, 1, 15)
        self.watchlist_entry = WatchlistEntry.create("AAPL", min_confidence=Decimal("0.6"))

    def create_market_data(self) -> MarketDataAcquireResult:
        bars = [
            PriceBar.create(
                symbol=self.symbol,
                session_date=self.as_of,
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("149.00"),
                close=Decimal("153.00"),
                volume=1000000,
            )
        ]
        return MarketDataAcquireResult(
            price_history={self.symbol: bars},
            fundamentals={},
            as_of=self.as_of,
        )

    def test_buy_when_all_scores_high(self):
        technical = TechnicalIndicators.create(
            symbol=self.symbol,
            as_of=self.as_of,
            rsi_14=Decimal("45"),
            macd_histogram=Decimal("1.0"),
            ema_12=Decimal("152.0"),
            ema_26=Decimal("150.0"),
            atr_14=Decimal("2.0"),
        )
        fundamental = FundamentalScore(
            symbol=self.symbol,
            score=Decimal("0.8"),
            factors=("low_pe", "high_roe"),
        )
        ml = MLScore.create(
            symbol=self.symbol,
            as_of=self.as_of,
            probability_up=Decimal("0.8"),
            model_version="v1.0.0",
            features_hash="abc",
        )
        market_data = self.create_market_data()

        rec = self.generator.generate(
            symbol=self.symbol,
            watchlist_entry=self.watchlist_entry,
            market_data=market_data,
            technical=technical,
            fundamental=fundamental,
            ml=ml,
        )

        assert rec is not None
        assert rec.action == RecommendationAction.BUY
        assert rec.confidence >= Decimal("0.6")
        assert rec.entry_price is not None
        assert rec.stop_loss is not None
        assert rec.target_price is not None

    def test_watch_when_moderate_scores(self):
        technical = TechnicalIndicators.create(
            symbol=self.symbol,
            as_of=self.as_of,
            rsi_14=Decimal("55"),
            macd_histogram=Decimal("0.1"),
            ema_12=Decimal("151.0"),
            ema_26=Decimal("150.5"),
        )
        fundamental = FundamentalScore(
            symbol=self.symbol,
            score=Decimal("0.55"),
            factors=(),
        )
        ml = MLScore.create(
            symbol=self.symbol,
            as_of=self.as_of,
            probability_up=Decimal("0.55"),
            model_version="v1.0.0",
            features_hash="abc",
        )
        market_data = self.create_market_data()

        rec = self.generator.generate(
            symbol=self.symbol,
            watchlist_entry=self.watchlist_entry,
            market_data=market_data,
            technical=technical,
            fundamental=fundamental,
            ml=ml,
        )

        assert rec is not None
        assert rec.action == RecommendationAction.WATCH
        assert Decimal("0.4") <= rec.confidence < Decimal("0.6")

    def test_avoid_when_low_scores(self):
        technical = TechnicalIndicators.create(
            symbol=self.symbol,
            as_of=self.as_of,
            rsi_14=Decimal("75"),
            macd_histogram=Decimal("-1.0"),
            ema_12=Decimal("148.0"),
            ema_26=Decimal("150.0"),
        )
        fundamental = FundamentalScore(
            symbol=self.symbol,
            score=Decimal("0.3"),
            factors=("high_pe", "high_debt"),
        )
        ml = MLScore.create(
            symbol=self.symbol,
            as_of=self.as_of,
            probability_up=Decimal("0.3"),
            model_version="v1.0.0",
            features_hash="abc",
        )
        market_data = self.create_market_data()

        rec = self.generator.generate(
            symbol=self.symbol,
            watchlist_entry=self.watchlist_entry,
            market_data=market_data,
            technical=technical,
            fundamental=fundamental,
            ml=ml,
        )

        assert rec is not None
        assert rec.action == RecommendationAction.AVOID

    def test_returns_none_for_empty_price_history(self):
        market_data = MarketDataAcquireResult(
            price_history={self.symbol: []},
            fundamentals={},
            as_of=self.as_of,
        )

        rec = self.generator.generate(
            symbol=self.symbol,
            watchlist_entry=self.watchlist_entry,
            market_data=market_data,
            technical=None,
            fundamental=None,
            ml=None,
        )

        assert rec is None

    def test_custom_weights(self):
        weights = ScoringWeights(
            technical=Decimal("0.5"),
            fundamental=Decimal("0.3"),
            ml=Decimal("0.2"),
        )
        generator = DefaultRecommendationGenerator(weights=weights)
        assert generator._weights.technical == Decimal("0.5")


class TestRecommendationGenerationCapability:
    def setup_method(self):
        self.capability = RecommendationGenerationCapability()

    def test_execute_with_all_data(self):
        symbol = StockSymbol("AAPL")
        as_of = date(2024, 1, 15)

        watchlist = Watchlist.create(
            name="Test",
            entries=[WatchlistEntry.create("AAPL")],
        )

        bars = [PriceBar.create(
            symbol=symbol,
            session_date=as_of,
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("153.00"),
            volume=1000000,
        )]

        market_data = MarketDataAcquireResult(
            price_history={symbol: bars},
            fundamentals={},
            as_of=as_of,
        )

        technical = TechnicalIndicators.create(
            symbol=symbol,
            as_of=as_of,
            rsi_14=Decimal("40"),
            macd_histogram=Decimal("0.5"),
            ema_12=Decimal("152.0"),
            ema_26=Decimal("150.0"),
            atr_14=Decimal("2.0"),
        )

        fundamental = FundamentalScore(
            symbol=symbol,
            score=Decimal("0.7"),
            factors=("low_pe",),
        )

        ml = MLScore.create(
            symbol=symbol,
            as_of=as_of,
            probability_up=Decimal("0.75"),
            model_version="v1.0.0",
            features_hash="abc",
        )

        context = ExecutionContext()
        context.set("watchlist", watchlist)
        context.set("market_data", market_data)
        context.set("technical_indicators", {symbol: technical})
        context.set("fundamental_scores", {symbol: fundamental})
        context.set("ml_scores", {symbol: ml})

        result = self.capability.execute(context)
        assert result.succeeded is True

        recommendations = context.get("recommendations")
        assert len(recommendations) == 1
        assert recommendations[0].symbol == symbol
        assert recommendations[0].action == RecommendationAction.BUY

    def test_execute_sorts_by_confidence_desc(self):
        watchlist = Watchlist.create(
            name="Test",
            entries=[
                WatchlistEntry.create("AAPL"),
                WatchlistEntry.create("MSFT"),
            ],
        )

        as_of = date(2024, 1, 15)
        symbols = [StockSymbol("AAPL"), StockSymbol("MSFT")]

        bars_aapl = [PriceBar.create(symbol=symbols[0], session_date=as_of, open=Decimal("150"), high=Decimal("155"), low=Decimal("149"), close=Decimal("153"), volume=1000000)]
        bars_msft = [PriceBar.create(symbol=symbols[1], session_date=as_of, open=Decimal("300"), high=Decimal("310"), low=Decimal("299"), close=Decimal("305"), volume=1000000)]

        market_data = MarketDataAcquireResult(
            price_history={symbols[0]: bars_aapl, symbols[1]: bars_msft},
            fundamentals={},
            as_of=as_of,
        )

        # AAPL gets high scores -> BUY
        tech_aapl = TechnicalIndicators.create(symbol=symbols[0], as_of=as_of, rsi_14=Decimal("40"), macd_histogram=Decimal("1.0"), ema_12=Decimal("152"), ema_26=Decimal("150"), atr_14=Decimal("2"))
        fund_aapl = FundamentalScore(symbol=symbols[0], score=Decimal("0.8"), factors=())
        ml_aapl = MLScore.create(symbol=symbols[0], as_of=as_of, probability_up=Decimal("0.8"), model_version="v1", features_hash="abc")

        # MSFT gets moderate scores -> WATCH
        tech_msft = TechnicalIndicators.create(symbol=symbols[1], as_of=as_of, rsi_14=Decimal("55"), macd_histogram=Decimal("0.1"), ema_12=Decimal("301"), ema_26=Decimal("300"), atr_14=Decimal("3"))
        fund_msft = FundamentalScore(symbol=symbols[1], score=Decimal("0.55"), factors=())
        ml_msft = MLScore.create(symbol=symbols[1], as_of=as_of, probability_up=Decimal("0.55"), model_version="v1", features_hash="abc")

        context = ExecutionContext()
        context.set("watchlist", watchlist)
        context.set("market_data", market_data)
        context.set("technical_indicators", {symbols[0]: tech_aapl, symbols[1]: tech_msft})
        context.set("fundamental_scores", {symbols[0]: fund_aapl, symbols[1]: fund_msft})
        context.set("ml_scores", {symbols[0]: ml_aapl, symbols[1]: ml_msft})

        result = self.capability.execute(context)
        assert result.succeeded is True

        recommendations = context.get("recommendations")
        assert len(recommendations) == 2
        # AAPL should come first (higher confidence)
        assert recommendations[0].symbol == StockSymbol("AAPL")
        assert recommendations[1].symbol == StockSymbol("MSFT")

    def test_execute_without_watchlist_fails(self):
        context = ExecutionContext()
        result = self.capability.execute(context)
        assert result.succeeded is False
