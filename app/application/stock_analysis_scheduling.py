from __future__ import annotations

from datetime import datetime, date, time, timedelta
from typing import Protocol
from uuid import UUID

from app.application.scheduling import Clock, ScheduledExecutionRequest
from app.application.stock_analysis_workflow import (
    StockAnalysisWorkflowComposition,
    create_daily_analysis_workflow,
    create_morning_delivery_workflow,
    create_default_watchlist,
    create_default_email_config,
    create_default_push_config,
)
from app.domain.workflow import Workflow
from app.domain.stock_analysis import Watchlist, EmailConfig, PushConfig
from app.domain.repositories import WorkflowRepository


class TradingCalendar(Protocol):
    """Protocol for checking trading days."""

    def is_trading_day(self, dt: date) -> bool:
        ...

    def next_trading_day(self, dt: date) -> date:
        ...


class USATradingCalendar:
    """Simple US trading calendar (excludes weekends and major holidays)."""

    HOLIDAYS_2024 = {
        date(2024, 1, 1),   # New Year's Day
        date(2024, 1, 15),  # MLK Day
        date(2024, 2, 19),  # Presidents Day
        date(2024, 3, 29),  # Good Friday
        date(2024, 5, 27),  # Memorial Day
        date(2024, 6, 19),  # Juneteenth
        date(2024, 7, 4),   # Independence Day
        date(2024, 9, 2),   # Labor Day
        date(2024, 11, 28), # Thanksgiving
        date(2024, 12, 25), # Christmas
    }

    HOLIDAYS_2025 = {
        date(2025, 1, 1),
        date(2025, 1, 20),
        date(2025, 2, 17),
        date(2025, 4, 18),
        date(2025, 5, 26),
        date(2025, 6, 19),
        date(2025, 7, 4),
        date(2025, 9, 1),
        date(2025, 11, 27),
        date(2025, 12, 25),
    }

    def __init__(self) -> None:
        self._holidays = self.HOLIDAYS_2024 | self.HOLIDAYS_2025

    def is_trading_day(self, dt: date) -> bool:
        if dt.weekday() >= 5:
            return False
        if dt in self._holidays:
            return False
        return True

    def next_trading_day(self, dt: date) -> date:
        next_day = dt + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)
        return next_day


class StockAnalysisScheduler:
    """Schedules and manages stock analysis workflows."""

    MARKET_CLOSE_HOUR = 16
    MARKET_PREOPEN_HOUR = 8
    MARKET_PREOPEN_MINUTE = 30

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        composition: StockAnalysisWorkflowComposition,
        clock: Clock,
        calendar: TradingCalendar | None = None,
        watchlist: Watchlist | None = None,
        email_config: EmailConfig | None = None,
        push_config: PushConfig | None = None,
    ) -> None:
        self._workflow_repo = workflow_repository
        self._composition = composition
        self._clock = clock
        self._calendar = calendar or USATradingCalendar()
        self._watchlist = watchlist or create_default_watchlist()
        self._email_config = email_config or create_default_email_config()
        self._push_config = push_config or create_default_push_config()

        self._analysis_workflow_id: UUID | None = None
        self._delivery_workflow_id: UUID | None = None

    def ensure_workflows_published(self) -> tuple[UUID, UUID]:
        """Ensure both workflows exist and are published. Returns (analysis_id, delivery_id)."""
        if self._analysis_workflow_id is None:
            analysis_def = create_daily_analysis_workflow(
                self._watchlist, self._email_config, self._push_config
            )
            analysis_workflow = Workflow.create(**analysis_def)
            analysis_workflow.publish()
            self._workflow_repo.save(analysis_workflow)
            self._analysis_workflow_id = analysis_workflow.id

        if self._delivery_workflow_id is None:
            delivery_def = create_morning_delivery_workflow(
                self._watchlist, self._email_config, self._push_config
            )
            delivery_workflow = Workflow.create(**delivery_def)
            delivery_workflow.publish()
            self._workflow_repo.save(delivery_workflow)
            self._delivery_workflow_id = delivery_workflow.id

        return self._analysis_workflow_id, self._delivery_workflow_id

    def schedule_today(self) -> list[ScheduledExecutionRequest]:
        """Create scheduled execution requests for today (if trading day)."""
        today = self._clock.now().date()

        if not self._calendar.is_trading_day(today):
            return []

        self.ensure_workflows_published()

        requests = []

        analysis_time = datetime.combine(today, time(self.MARKET_CLOSE_HOUR, 0))
        if self._clock.now() < analysis_time:
            requests.append(
                ScheduledExecutionRequest.create(
                    workflow_id=self._analysis_workflow_id,
                    scheduled_at=analysis_time,
                )
            )

        next_trading_day = self._calendar.next_trading_day(today)
        delivery_time = datetime.combine(
            next_trading_day,
            time(self.MARKET_PREOPEN_HOUR, self.MARKET_PREOPEN_MINUTE),
        )
        if self._clock.now() < delivery_time:
            requests.append(
                ScheduledExecutionRequest.create(
                    workflow_id=self._delivery_workflow_id,
                    scheduled_at=delivery_time,
                )
            )

        return requests

    def get_schedule_for_range(self, start_date: date, end_date: date) -> list[ScheduledExecutionRequest]:
        """Get all scheduled executions for a date range."""
        requests = []
        current = start_date
        while current <= end_date:
            if self._calendar.is_trading_day(current):
                analysis_time = datetime.combine(current, time(self.MARKET_CLOSE_HOUR, 0))
                if self._clock.now() < analysis_time:
                    requests.append(
                        ScheduledExecutionRequest.create(
                            workflow_id=self._analysis_workflow_id or UUID(int=0),
                            scheduled_at=analysis_time,
                        )
                    )

                next_day = self._calendar.next_trading_day(current)
                delivery_time = datetime.combine(
                    next_day,
                    time(self.MARKET_PREOPEN_HOUR, self.MARKET_PREOPEN_MINUTE),
                )
                if self._clock.now() < delivery_time:
                    requests.append(
                        ScheduledExecutionRequest.create(
                            workflow_id=self._delivery_workflow_id or UUID(int=0),
                            scheduled_at=delivery_time,
                        )
                    )
            current += timedelta(days=1)
        return requests