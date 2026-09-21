"""Tests for stock analysis workflow and scheduling."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from app.application.scheduling import FixedClock
from app.application.stock_analysis_scheduling import (
    StockAnalysisScheduler,
    USATradingCalendar,
)
from app.application.stock_analysis_workflow import (
    create_daily_analysis_workflow,
    create_default_email_config,
    create_default_push_config,
    create_default_watchlist,
    create_morning_delivery_workflow,
)
from app.domain.stock_analysis import (
    EmailConfig,
    PushConfig,
    Watchlist,
    WatchlistEntry,
)
from app.infrastructure.persistence.in_memory import InMemoryWorkflowRepository


class TestWorkflowCreation:
    def test_create_daily_analysis_workflow(self):
        watchlist = Watchlist.create(name="Test", entries=[WatchlistEntry.create("AAPL")])
        email_config = EmailConfig(
            smtp_host="smtp.test.com", smtp_port=587,
            username="user", password="pass",
            from_email="from@test.com", to_emails=("to@test.com",)
        )

        workflow_def = create_daily_analysis_workflow(watchlist, email_config, None)

        assert workflow_def["name"] == "Daily Stock Analysis - Test"
        assert len(workflow_def["steps"]) == 5
        assert workflow_def["steps"][0].capability == "market_data_acquire"
        assert workflow_def["steps"][1].capability == "technical_analysis"
        assert workflow_def["steps"][2].capability == "fundamental_analysis"
        assert workflow_def["steps"][3].capability == "ml_scoring"
        assert workflow_def["steps"][4].capability == "recommendation_generation"
        assert "watchlist" in workflow_def["required_parameters"]
        assert "email_config" in workflow_def["required_parameters"]

    def test_create_morning_delivery_workflow_email_only(self):
        watchlist = Watchlist.create(name="Test", entries=[WatchlistEntry.create("AAPL")])
        email_config = EmailConfig(
            smtp_host="smtp.test.com", smtp_port=587,
            username="user", password="pass",
            from_email="from@test.com", to_emails=("to@test.com",)
        )

        workflow_def = create_morning_delivery_workflow(watchlist, email_config, None)

        assert workflow_def["name"] == "Morning Delivery - Test"
        assert len(workflow_def["steps"]) == 1
        assert workflow_def["steps"][0].capability == "email_notification"

    def test_create_morning_delivery_workflow_push_only(self):
        watchlist = Watchlist.create(name="Test", entries=[WatchlistEntry.create("AAPL")])
        push_config = PushConfig(provider="ntfy", api_key="", topic="test")

        workflow_def = create_morning_delivery_workflow(watchlist, None, push_config)

        assert len(workflow_def["steps"]) == 1
        assert workflow_def["steps"][0].capability == "push_notification"

    def test_create_morning_delivery_workflow_both(self):
        watchlist = Watchlist.create(name="Test", entries=[WatchlistEntry.create("AAPL")])
        email_config = EmailConfig(
            smtp_host="smtp.test.com", smtp_port=587,
            username="user", password="pass",
            from_email="from@test.com", to_emails=("to@test.com",)
        )
        push_config = PushConfig(provider="ntfy", api_key="", topic="test")

        workflow_def = create_morning_delivery_workflow(watchlist, email_config, push_config)

        assert len(workflow_def["steps"]) == 2
        caps = {s.capability for s in workflow_def["steps"]}
        assert caps == {"email_notification", "push_notification"}

    def test_create_morning_delivery_workflow_none_raises(self):
        watchlist = Watchlist.create(name="Test", entries=[WatchlistEntry.create("AAPL")])
        with pytest.raises(ValueError, match="notification channel"):
            create_morning_delivery_workflow(watchlist, None, None)


class TestDefaultConfigs:
    def test_create_default_watchlist(self):
        watchlist = create_default_watchlist()
        assert watchlist.name == "US Large Cap"
        assert len(watchlist.entries) == 20
        assert all(e.enabled for e in watchlist.entries)

    def test_create_default_email_config(self):
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.custom.com",
            "SMTP_PORT": "465",
            "SMTP_USERNAME": "custom_user",
            "SMTP_PASSWORD": "custom_pass",
            "SMTP_FROM": "custom@test.com",
            "SMTP_TO": "to1@test.com,to2@test.com",
            "SMTP_TLS": "false",
        }, clear=True):
            config = create_default_email_config()
            assert config.smtp_host == "smtp.custom.com"
            assert config.smtp_port == 465
            assert config.username == "custom_user"
            assert config.to_emails == ("to1@test.com", "to2@test.com")
            assert config.use_tls is False

    def test_create_default_push_config(self):
        with patch.dict("os.environ", {
            "PUSH_PROVIDER": "firebase",
            "PUSH_API_KEY": "firebase_key",
            "PUSH_APP_ID": "app123",
            "PUSH_TOPIC": "custom_topic",
            "PUSH_TOKENS": "token1,token2",
        }, clear=True):
            config = create_default_push_config()
            assert config.provider == "firebase"
            assert config.api_key == "firebase_key"
            assert config.app_id == "app123"
            assert config.topic == "custom_topic"
            assert config.user_tokens == ("token1", "token2")


class TestUSATradingCalendar:
    def setup_method(self):
        self.calendar = USATradingCalendar()

    def test_weekday_is_trading_day(self):
        # Monday Jan 15, 2024 (MLK Day - holiday)
        assert self.calendar.is_trading_day(date(2024, 1, 16)) is True  # Tuesday
        assert self.calendar.is_trading_day(date(2024, 1, 17)) is True  # Wednesday

    def test_weekend_is_not_trading_day(self):
        # Jan 13-14, 2024 is weekend
        assert self.calendar.is_trading_day(date(2024, 1, 13)) is False  # Saturday
        assert self.calendar.is_trading_day(date(2024, 1, 14)) is False  # Sunday

    def test_holiday_is_not_trading_day(self):
        assert self.calendar.is_trading_day(date(2024, 1, 1)) is False   # New Year
        assert self.calendar.is_trading_day(date(2024, 7, 4)) is False   # Independence Day
        assert self.calendar.is_trading_day(date(2024, 12, 25)) is False # Christmas

    def test_next_trading_day_skips_weekend(self):
        friday = date(2024, 1, 12)
        next_day = self.calendar.next_trading_day(friday)
        assert next_day == date(2024, 1, 16)  # Monday (15th is MLK holiday)

    def test_next_trading_day_skips_holiday(self):
        # Jan 14 is Sunday, Jan 15 is MLK Day
        sunday = date(2024, 1, 14)
        next_day = self.calendar.next_trading_day(sunday)
        assert next_day == date(2024, 1, 16)  # Tuesday


class TestStockAnalysisScheduler:
    def setup_method(self):
        self.workflow_repo = InMemoryWorkflowRepository()
        self.composition = Mock()
        self.clock = FixedClock(datetime(2024, 1, 16, 10, 0))  # Tuesday 10 AM
        self.calendar = USATradingCalendar()
        self.watchlist = Watchlist.create(name="Test", entries=[WatchlistEntry.create("AAPL")])
        self.email_config = EmailConfig(
            smtp_host="smtp.test.com", smtp_port=587,
            username="user", password="pass",
            from_email="from@test.com", to_emails=("to@test.com",)
        )
        self.push_config = PushConfig(provider="ntfy", api_key="", topic="test")

    def test_schedule_today_on_trading_day(self):
        scheduler = StockAnalysisScheduler(
            workflow_repository=self.workflow_repo,
            composition=self.composition,
            clock=self.clock,
            calendar=self.calendar,
            watchlist=self.watchlist,
            email_config=self.email_config,
            push_config=self.push_config,
        )

        requests = scheduler.schedule_today()
        assert len(requests) == 2  # Analysis today + delivery tomorrow

        # Check analysis is scheduled for today 16:00
        analysis_req = next(r for r in requests if r.scheduled_at.hour == 16)
        assert analysis_req.scheduled_at.date() == date(2024, 1, 16)

        # Check delivery is scheduled for next trading day 08:30
        delivery_req = next(r for r in requests if r.scheduled_at.hour == 8)
        assert delivery_req.scheduled_at == datetime(2024, 1, 17, 8, 30)

    def test_schedule_today_on_weekend_returns_empty(self):
        weekend_clock = FixedClock(datetime(2024, 1, 13, 10, 0))  # Saturday
        scheduler = StockAnalysisScheduler(
            workflow_repository=self.workflow_repo,
            composition=self.composition,
            clock=weekend_clock,
            calendar=self.calendar,
            watchlist=self.watchlist,
            email_config=self.email_config,
            push_config=self.push_config,
        )

        requests = scheduler.schedule_today()
        assert len(requests) == 0

    def test_schedule_today_on_holiday_returns_empty(self):
        holiday_clock = FixedClock(datetime(2024, 7, 4, 10, 0))  # Independence Day
        scheduler = StockAnalysisScheduler(
            workflow_repository=self.workflow_repo,
            composition=self.composition,
            clock=holiday_clock,
            calendar=self.calendar,
            watchlist=self.watchlist,
            email_config=self.email_config,
            push_config=self.push_config,
        )

        requests = scheduler.schedule_today()
        assert len(requests) == 0

    def test_schedule_past_time_not_included(self):
        # Clock is after market close
        late_clock = FixedClock(datetime(2024, 1, 16, 17, 0))  # 5 PM
        scheduler = StockAnalysisScheduler(
            workflow_repository=self.workflow_repo,
            composition=self.composition,
            clock=late_clock,
            calendar=self.calendar,
            watchlist=self.watchlist,
            email_config=self.email_config,
            push_config=self.push_config,
        )

        requests = scheduler.schedule_today()
        # Analysis for today should not be scheduled (past 16:00)
        # But delivery for tomorrow should be
        assert len(requests) == 1
        delivery_req = requests[0]
        assert delivery_req.scheduled_at == datetime(2024, 1, 17, 8, 30)

    def test_ensure_workflows_published(self):
        scheduler = StockAnalysisScheduler(
            workflow_repository=self.workflow_repo,
            composition=self.composition,
            clock=self.clock,
            calendar=self.calendar,
            watchlist=self.watchlist,
            email_config=self.email_config,
            push_config=self.push_config,
        )

        analysis_id, delivery_id = scheduler.ensure_workflows_published()

        assert isinstance(analysis_id, UUID)
        assert isinstance(delivery_id, UUID)

        analysis_workflow = self.workflow_repo.get(analysis_id)
        delivery_workflow = self.workflow_repo.get(delivery_id)

        assert analysis_workflow.state.name == "PUBLISHED"
        assert delivery_workflow.state.name == "PUBLISHED"
        assert len(analysis_workflow.steps) == 5
        assert len(delivery_workflow.steps) == 2
