"""Tests for stock analysis domain models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.stock_analysis import (
    EmailConfig,
    FundamentalMetrics,
    MLScore,
    PriceBar,
    PushConfig,
    Recommendation,
    RecommendationAction,
    StockSymbol,
    TechnicalIndicators,
    Watchlist,
    WatchlistEntry,
)


class TestStockSymbol:
    def test_valid_symbol(self):
        symbol = StockSymbol.create("AAPL")
        assert str(symbol) == "AAPL"

    def test_symbol_normalization(self):
        symbol = StockSymbol.create("  aapl  ")
        assert str(symbol) == "AAPL"

    def test_symbol_with_special_chars(self):
        symbol = StockSymbol.create("BRK.B")
        assert str(symbol) == "BRK.B"

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError):
            StockSymbol.create("")

    def test_invalid_chars_raises(self):
        with pytest.raises(ValueError):
            StockSymbol.create("AAPL@")

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            StockSymbol.create(123)


class TestPriceBar:
    def test_valid_price_bar(self):
        bar = PriceBar.create(
            symbol="AAPL",
            session_date=date(2024, 1, 15),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("153.00"),
            volume=1000000,
        )
        assert bar.symbol == StockSymbol("AAPL")
        assert bar.close == Decimal("153.00")

    def test_high_less_than_low_raises(self):
        with pytest.raises(ValueError):
            PriceBar.create(
                symbol="AAPL",
                session_date=date(2024, 1, 15),
                open=Decimal("150.00"),
                high=Decimal("149.00"),
                low=Decimal("155.00"),
                close=Decimal("153.00"),
                volume=1000000,
            )

    def test_open_out_of_range_raises(self):
        with pytest.raises(ValueError):
            PriceBar.create(
                symbol="AAPL",
                session_date=date(2024, 1, 15),
                open=Decimal("160.00"),
                high=Decimal("155.00"),
                low=Decimal("149.00"),
                close=Decimal("153.00"),
                volume=1000000,
            )

    def test_negative_volume_raises(self):
        with pytest.raises(ValueError):
            PriceBar.create(
                symbol="AAPL",
                session_date=date(2024, 1, 15),
                open=Decimal("150.00"),
                high=Decimal("155.00"),
                low=Decimal("149.00"),
                close=Decimal("153.00"),
                volume=-100,
            )


class TestTechnicalIndicators:
    def test_create_with_all_fields(self):
        indicators = TechnicalIndicators.create(
            symbol="AAPL",
            as_of=date(2024, 1, 15),
            rsi_14=Decimal("65.5"),
            macd_line=Decimal("2.5"),
            sma_20=Decimal("150.0"),
        )
        assert indicators.rsi_14 == Decimal("65.5")
        assert indicators.macd_line == Decimal("2.5")
        assert indicators.sma_20 == Decimal("150.0")
        assert indicators.ema_12 is None

    def test_optional_fields_default_to_none(self):
        indicators = TechnicalIndicators.create(symbol="AAPL", as_of=date(2024, 1, 15))
        assert indicators.rsi_14 is None
        assert indicators.bb_upper is None


class TestFundamentalMetrics:
    def test_create_with_metrics(self):
        metrics = FundamentalMetrics.create(
            symbol="AAPL",
            as_of=date(2024, 1, 15),
            pe_ratio=Decimal("25.5"),
            roe=Decimal("0.35"),
        )
        assert metrics.pe_ratio == Decimal("25.5")
        assert metrics.roe == Decimal("0.35")
        assert metrics.pb_ratio is None


class TestMLScore:
    def test_valid_probability(self):
        score = MLScore.create(
            symbol="AAPL",
            as_of=date(2024, 1, 15),
            probability_up=Decimal("0.75"),
            model_version="v1.0.0",
            features_hash="abc123",
        )
        assert score.probability_up == Decimal("0.75")

    def test_probability_out_of_range_raises(self):
        with pytest.raises(ValueError):
            MLScore.create(
                symbol="AAPL",
                as_of=date(2024, 1, 15),
                probability_up=Decimal("1.5"),
                model_version="v1.0.0",
                features_hash="abc123",
            )

    def test_empty_model_version_raises(self):
        with pytest.raises(ValueError):
            MLScore.create(
                symbol="AAPL",
                as_of=date(2024, 1, 15),
                probability_up=Decimal("0.5"),
                model_version="",
                features_hash="abc123",
            )


class TestRecommendation:
    def test_buy_recommendation(self):
        rec = Recommendation.create(
            symbol="AAPL",
            action=RecommendationAction.BUY,
            confidence=Decimal("0.8"),
            rationale=["Strong technicals", "Good fundamentals"],
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            target_price=Decimal("160.00"),
        )
        assert rec.action == RecommendationAction.BUY
        assert rec.confidence == Decimal("0.8")
        assert rec.stop_loss == Decimal("145.00")

    def test_watch_recommendation(self):
        rec = Recommendation.create(
            symbol="MSFT",
            action=RecommendationAction.WATCH,
            confidence=Decimal("0.55"),
            rationale=["Neutral signals"],
        )
        assert rec.action == RecommendationAction.WATCH
        assert rec.entry_price is None

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValueError):
            Recommendation.create(
                symbol="AAPL",
                action=RecommendationAction.BUY,
                confidence=Decimal("1.5"),
                rationale=[],
            )


class TestWatchlistEntry:
    def test_default_values(self):
        entry = WatchlistEntry.create("AAPL")
        assert entry.enabled is True
        assert entry.min_confidence == Decimal("0.6")
        assert entry.custom_params == {}

    def test_custom_values(self):
        entry = WatchlistEntry.create(
            symbol="AAPL",
            enabled=False,
            min_confidence=Decimal("0.8"),
            custom_params={"sector": "tech"},
        )
        assert entry.enabled is False
        assert entry.min_confidence == Decimal("0.8")
        assert entry.custom_params == {"sector": "tech"}


class TestWatchlist:
    def test_create_watchlist(self):
        entries = [
            WatchlistEntry.create("AAPL"),
            WatchlistEntry.create("MSFT"),
        ]
        watchlist = Watchlist.create(name="Tech Stocks", entries=entries)
        assert watchlist.name == "Tech Stocks"
        assert len(watchlist.entries) == 2

    def test_duplicate_symbols_raises(self):
        entries = [
            WatchlistEntry.create("AAPL"),
            WatchlistEntry.create("AAPL"),
        ]
        with pytest.raises(ValueError):
            Watchlist.create(name="Test", entries=entries)

    def test_enabled_symbols(self):
        entries = [
            WatchlistEntry.create("AAPL", enabled=True),
            WatchlistEntry.create("MSFT", enabled=False),
            WatchlistEntry.create("GOOGL", enabled=True),
        ]
        watchlist = Watchlist.create(name="Test", entries=entries)
        enabled = watchlist.enabled_symbols()
        assert len(enabled) == 2
        assert StockSymbol("AAPL") in enabled
        assert StockSymbol("GOOGL") in enabled
        assert StockSymbol("MSFT") not in enabled


class TestEmailConfig:
    def test_valid_config(self):
        config = EmailConfig(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            username="user",
            password="pass",
            from_email="from@test.com",
            to_emails=("to@test.com",),
        )
        assert config.smtp_host == "smtp.gmail.com"

    def test_empty_smtp_host_raises(self):
        with pytest.raises(ValueError):
            EmailConfig(
                smtp_host="",
                smtp_port=587,
                username="user",
                password="pass",
                from_email="from@test.com",
                to_emails=("to@test.com",),
            )

    def test_empty_to_emails_raises(self):
        with pytest.raises(ValueError):
            EmailConfig(
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                username="user",
                password="pass",
                from_email="from@test.com",
                to_emails=(),
            )


class TestPushConfig:
    def test_valid_config(self):
        config = PushConfig(
            provider="ntfy",
            api_key="key",
            topic="alerts",
        )
        assert config.provider == "ntfy"

    def test_empty_provider_raises(self):
        with pytest.raises(ValueError):
            PushConfig(
                provider="",
                api_key="key",
            )
