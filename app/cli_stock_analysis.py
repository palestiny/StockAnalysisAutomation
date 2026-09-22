#!/usr/bin/env python3
"""Stock Analysis Automation CLI"""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.application.scheduling import FixedClock
from app.application.stock_analysis_config import StockAnalysisConfig
from app.application.stock_analysis_scheduling import StockAnalysisScheduler
from app.application.stock_analysis_workflow import (
    StockAnalysisWorkflowComposition,
    create_default_email_config,
    create_default_push_config,
    create_default_watchlist,
)
from app.domain.stock_analysis import Recommendation
from app.domain.workflow import Workflow
from app.infrastructure.capabilities.stock_analysis.email_notification import (
    EmailNotificationCapability,
)
from app.infrastructure.capabilities.stock_analysis.fundamental_analysis import (
    FundamentalAnalysisCapability,
)
from app.infrastructure.capabilities.stock_analysis.market_data_acquire import (
    MarketDataAcquireCapability,
)
from app.infrastructure.capabilities.stock_analysis.ml_scoring import MLScoringCapability
from app.infrastructure.capabilities.stock_analysis.push_notification import (
    PushNotificationCapability,
)
from app.infrastructure.capabilities.stock_analysis.recommendation_generation import (
    RecommendationGenerationCapability,
)
from app.infrastructure.capabilities.stock_analysis.technical_analysis import (
    TechnicalAnalysisCapability,
)
from app.infrastructure.persistence.in_memory import (
    InMemoryExecutionRepository,
    InMemoryWorkflowRepository,
)


def run_analysis_now(args):
    """Run the daily analysis workflow immediately."""
    print("[ANALYSIS] Running daily stock analysis...")

    config = StockAnalysisConfig()
    watchlist = config.load_watchlist() or create_default_watchlist()
    email_config = config.load_email_config() or create_default_email_config()
    push_config = config.load_push_config() or create_default_push_config()

    print(f"[WATCHLIST] {watchlist.name} ({len(watchlist.enabled_symbols())} symbols)")
    print(f"[EMAIL] {'configured' if email_config.to_emails else 'not configured'}")
    print(f"[PUSH] {'configured' if push_config.api_key or push_config.provider == 'ntfy' else 'not configured'}")

    workflow_repo = InMemoryWorkflowRepository()
    execution_repo = InMemoryExecutionRepository()

    use_cache = not getattr(args, "no_cache", False)
    print(f"[CACHE] {'enabled' if use_cache else 'disabled'}")

    market_data = MarketDataAcquireCapability(use_cache=use_cache)
    technical = TechnicalAnalysisCapability()
    fundamental = FundamentalAnalysisCapability()
    ml = MLScoringCapability()
    recommendation = RecommendationGenerationCapability()
    email = EmailNotificationCapability()
    push = PushNotificationCapability()

    composition = StockAnalysisWorkflowComposition(
        workflow_repository=workflow_repo,
        execution_repository=execution_repo,
        market_data_acquire=market_data,
        technical_analysis=technical,
        fundamental_analysis=fundamental,
        ml_scoring=ml,
        recommendation_generation=recommendation,
        email_notification=email,
        push_notification=push,
    )

    from app.application.stock_analysis_workflow import create_daily_analysis_workflow
    analysis_def = create_daily_analysis_workflow(watchlist, email_config, push_config)
    analysis_workflow = Workflow.create(**analysis_def)
    analysis_workflow.publish()
    workflow_repo.save(analysis_workflow)

    from app.application.execution_context import ExecutionContext
    exec_context = ExecutionContext()
    exec_context.set("watchlist", watchlist)
    exec_context.set("email_config", email_config)
    exec_context.set("push_config", push_config)

    print("\n[1/5] Acquiring market data...")
    market_data.execute(exec_context)

    print("[2/5] Computing technical indicators...")
    technical.execute(exec_context)

    print("[3/5] Analyzing fundamentals...")
    fundamental.execute(exec_context)

    print("[4/5] Running ML scoring...")
    ml.execute(exec_context)

    print("[5/5] Generating recommendations...")
    recommendation.execute(exec_context)

    recommendations: list[Recommendation] = exec_context.get("recommendations")  # type: ignore[assignment]
    print(f"\n[OK] Analysis complete! Generated {len(recommendations)} recommendations")

    buy_recs: list[Recommendation] = [r for r in recommendations if r.action.value == "buy"]  # type: ignore[misc]
    watch_recs: list[Recommendation] = [r for r in recommendations if r.action.value == "watch"]  # type: ignore[misc]

    if buy_recs:
        print(f"\n[BUY] ({len(buy_recs)}):")
        for r in buy_recs[:5]:
            print(f"  {r.symbol}: {r.confidence:.1%} - Entry: ${r.entry_price:.2f}, Stop: ${r.stop_loss:.2f}, Target: ${r.target_price:.2f}")

    if watch_recs:
        print(f"\n[WATCH] ({len(watch_recs)}):")
        for r in watch_recs[:5]:
            print(f"  {r.symbol}: {r.confidence:.1%}")

    if email_config.to_emails:
        print("\n[EMAIL] Sending email notification...")
        email.execute(exec_context)
        if exec_context.get_or_none("email_sent") is True:
            print("[OK] Email sent successfully")
        else:
            print("[FAIL] Email failed")

    if push_config.api_key or push_config.provider == "ntfy":
        print("\n[PUSH] Sending push notification...")
        push.execute(exec_context)
        if exec_context.get_or_none("push_sent") is True:
            print("[OK] Push sent successfully")
        else:
            print("[FAIL] Push failed")

    print("\n[DONE] Done!")


def run_delivery_now(args):
    """Run the morning delivery workflow immediately."""
    print("[DELIVERY] Running morning delivery...")

    config = StockAnalysisConfig()
    watchlist = config.load_watchlist() or create_default_watchlist()
    email_config = config.load_email_config() or create_default_email_config()
    push_config = config.load_push_config() or create_default_push_config()

    if not email_config.to_emails and not (push_config.api_key or push_config.provider == "ntfy"):
        print("[FAIL] No notification channels configured")
        return

    workflow_repo = InMemoryWorkflowRepository()
    execution_repo = InMemoryExecutionRepository()

    email = EmailNotificationCapability()
    push = PushNotificationCapability()

    from app.application.stock_analysis_workflow import create_morning_delivery_workflow
    delivery_def = create_morning_delivery_workflow(watchlist, email_config, push_config)
    delivery_workflow = Workflow.create(**delivery_def)
    delivery_workflow.publish()
    workflow_repo.save(delivery_workflow)

    from app.application.capability_dispatcher import CapabilityDispatcher
    from app.application.capability_registry import CapabilityRegistry
    from app.application.condition_evaluator import ConditionEvaluator
    from app.application.execute_workflow_step import ExecuteWorkflowStep
    from app.application.start_workflow_execution import StartWorkflowExecution

    registry = CapabilityRegistry()
    registry.register("email_notification", email)
    registry.register("push_notification", push)
    dispatcher = CapabilityDispatcher(registry)

    start = StartWorkflowExecution(workflow_repo, execution_repo)
    execute_step = ExecuteWorkflowStep(workflow_repo, execution_repo, dispatcher, ConditionEvaluator())

    execution = start.execute(delivery_workflow.id)

    from app.application.execution_context import ExecutionContext
    context = ExecutionContext()
    context.set("watchlist", watchlist)
    context.set("email_config", email_config)
    context.set("push_config", push_config)

    from app.domain.stock_analysis import Recommendation, RecommendationAction
    mock_recs = [
        Recommendation.create("AAPL", RecommendationAction.BUY, Decimal("0.75"), ["Test"], Decimal("150"), Decimal("145"), Decimal("160")),
        Recommendation.create("MSFT", RecommendationAction.BUY, Decimal("0.72"), ["Test"], Decimal("300"), Decimal("290"), Decimal("320")),
    ]
    context.set("recommendations", mock_recs)

    for step in delivery_workflow.steps:
        print(f"  Executing: {step.name} ({step.capability})")
        execute_step.execute(execution.id, context)

    print("[OK] Delivery complete!")


def schedule_daemon(args):
    """Run the scheduler daemon."""
    print("[SCHEDULER] Starting stock analysis scheduler...")
    print("Press Ctrl+C to stop")

    config = StockAnalysisConfig()
    watchlist = config.load_watchlist() or create_default_watchlist()
    email_config = config.load_email_config() or create_default_email_config()
    push_config = config.load_push_config() or create_default_push_config()

    workflow_repo = InMemoryWorkflowRepository()
    execution_repo = InMemoryExecutionRepository()

    market_data = MarketDataAcquireCapability()
    technical = TechnicalAnalysisCapability()
    fundamental = FundamentalAnalysisCapability()
    ml = MLScoringCapability()
    recommendation = RecommendationGenerationCapability()
    email = EmailNotificationCapability()
    push = PushNotificationCapability()

    composition = StockAnalysisWorkflowComposition(
        workflow_repository=workflow_repo,
        execution_repository=execution_repo,
        market_data_acquire=market_data,
        technical_analysis=technical,
        fundamental_analysis=fundamental,
        ml_scoring=ml,
        recommendation_generation=recommendation,
        email_notification=email,
        push_notification=push,
    )

    clock = FixedClock(datetime.now())
    scheduler = StockAnalysisScheduler(
        workflow_repository=workflow_repo,
        composition=composition,
        clock=clock,
        watchlist=watchlist,
        email_config=email_config,
        push_config=push_config,
    )

    requests = scheduler.schedule_today()
    print(f"[SCHEDULE] Scheduled {len(requests)} executions for today")

    for req in requests:
        print(f"  - {req.workflow_id} at {req.scheduled_at}")

    print("\n[TIP] To run as a daemon, integrate with the platform's scheduling engine")
    print("   or use a cron job / systemd timer to run this script periodically.")


def init_config(args):
    """Initialize example configuration."""
    StockAnalysisConfig.create_example_config()
    print("\n[NOTE] Next steps:")
    print("1. Edit ~/.automation_os/stock_analysis/config.json with your email/push credentials")
    print("2. Edit ~/.automation_os/stock_analysis/watchlist.json to customize your watchlist")
    print("3. Run 'python -m app.cli_stock_analysis analyze' to test")


def main():
    parser = argparse.ArgumentParser(description="Stock Analysis Automation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Run daily analysis now")
    analyze_parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    analyze_parser.set_defaults(func=run_analysis_now)

    deliver_parser = subparsers.add_parser("deliver", help="Run morning delivery now")
    deliver_parser.set_defaults(func=run_delivery_now)

    schedule_parser = subparsers.add_parser("schedule", help="Run scheduler daemon")
    schedule_parser.set_defaults(func=schedule_daemon)

    init_parser = subparsers.add_parser("init", help="Create example configuration")
    init_parser.set_defaults(func=init_config)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
