from __future__ import annotations

from uuid import UUID

from app.application.capability import Capability
from app.application.capability_dispatcher import CapabilityDispatcher
from app.application.capability_registry import CapabilityRegistry
from app.application.condition_evaluator import ConditionEvaluator
from app.application.execute_workflow_step import ExecuteWorkflowStep
from app.application.execution_context import ExecutionContext
from app.application.start_workflow_execution import StartWorkflowExecution
from app.domain.execution import Execution
from app.domain.repositories import ExecutionRepository, WorkflowRepository
from app.domain.stock_analysis import EmailConfig, PushConfig, Watchlist

MARKET_DATA_ACQUIRE_CAPABILITY_ID = "market_data_acquire"
TECHNICAL_ANALYSIS_CAPABILITY_ID = "technical_analysis"
FUNDAMENTAL_ANALYSIS_CAPABILITY_ID = "fundamental_analysis"
ML_SCORING_CAPABILITY_ID = "ml_scoring"
RECOMMENDATION_GENERATION_CAPABILITY_ID = "recommendation_generation"
EMAIL_NOTIFICATION_CAPABILITY_ID = "email_notification"
PUSH_NOTIFICATION_CAPABILITY_ID = "push_notification"


class StockAnalysisWorkflowComposition:
    """Application composition for stock analysis workflows."""

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        execution_repository: ExecutionRepository,
        market_data_acquire: Capability,
        technical_analysis: Capability,
        fundamental_analysis: Capability,
        ml_scoring: Capability,
        recommendation_generation: Capability,
        email_notification: Capability,
        push_notification: Capability,
    ) -> None:
        registry = CapabilityRegistry()
        registry.register(MARKET_DATA_ACQUIRE_CAPABILITY_ID, market_data_acquire)
        registry.register(TECHNICAL_ANALYSIS_CAPABILITY_ID, technical_analysis)
        registry.register(FUNDAMENTAL_ANALYSIS_CAPABILITY_ID, fundamental_analysis)
        registry.register(ML_SCORING_CAPABILITY_ID, ml_scoring)
        registry.register(RECOMMENDATION_GENERATION_CAPABILITY_ID, recommendation_generation)
        registry.register(EMAIL_NOTIFICATION_CAPABILITY_ID, email_notification)
        registry.register(PUSH_NOTIFICATION_CAPABILITY_ID, push_notification)

        dispatcher = CapabilityDispatcher(registry)
        self._start = StartWorkflowExecution(
            workflow_repository,
            execution_repository,
        )
        self._execute_step = ExecuteWorkflowStep(
            workflow_repository,
            execution_repository,
            dispatcher,
            ConditionEvaluator(),
        )

    def start(self, workflow_id: UUID) -> Execution:
        return self._start.execute(workflow_id)

    def execute_step(self, execution_id: UUID, context: ExecutionContext) -> Execution:
        return self._execute_step.execute(execution_id, context)


def create_daily_analysis_workflow(
    watchlist: Watchlist,
    email_config: EmailConfig | None = None,
    push_config: PushConfig | None = None,
) -> dict:
    """Create workflow definition for daily analysis (runs after market close)."""
    from app.domain.workflow import Trigger, WorkflowParameter, WorkflowStep

    steps = [
        WorkflowStep.create(
            name="Acquire Market Data",
            capability=MARKET_DATA_ACQUIRE_CAPABILITY_ID,
        ),
        WorkflowStep.create(
            name="Technical Analysis",
            capability=TECHNICAL_ANALYSIS_CAPABILITY_ID,
        ),
        WorkflowStep.create(
            name="Fundamental Analysis",
            capability=FUNDAMENTAL_ANALYSIS_CAPABILITY_ID,
        ),
        WorkflowStep.create(
            name="ML Scoring",
            capability=ML_SCORING_CAPABILITY_ID,
        ),
        WorkflowStep.create(
            name="Generate Recommendations",
            capability=RECOMMENDATION_GENERATION_CAPABILITY_ID,
        ),
    ]

    triggers = [
        Trigger.create("daily_market_close"),
    ]

    required_params = ["watchlist"]
    param_types = [
        WorkflowParameter.create("watchlist", "string"),
    ]
    if email_config:
        required_params.append("email_config")
        param_types.append(WorkflowParameter.create("email_config", "string"))
    if push_config:
        required_params.append("push_config")
        param_types.append(WorkflowParameter.create("push_config", "string"))

    return {
        "name": f"Daily Stock Analysis - {watchlist.name}",
        "steps": steps,
        "triggers": triggers,
        "supported_goals": ["daily_stock_analysis"],
        "required_parameters": required_params,
        "parameter_types": param_types,
        "automation_domain": "stock_analysis",
        "discovery_tags": ["daily", "analysis", "stocks", watchlist.name.lower().replace(" ", "_")],
    }


def create_morning_delivery_workflow(
    watchlist: Watchlist,
    email_config: EmailConfig | None = None,
    push_config: PushConfig | None = None,
) -> dict:
    """Create workflow definition for morning delivery (runs before market open)."""
    from app.domain.workflow import Trigger, WorkflowParameter, WorkflowStep

    steps = []

    if email_config:
        steps.append(
            WorkflowStep.create(
                name="Send Email Notification",
                capability=EMAIL_NOTIFICATION_CAPABILITY_ID,
            )
        )

    if push_config:
        steps.append(
            WorkflowStep.create(
                name="Send Push Notification",
                capability=PUSH_NOTIFICATION_CAPABILITY_ID,
            )
        )

    if not steps:
        raise ValueError("At least one notification channel (email or push) must be configured")

    triggers = [
        Trigger.create("daily_market_preopen"),
    ]

    required_params = ["watchlist"]
    param_types = [
        WorkflowParameter.create("watchlist", "string"),
    ]
    if email_config:
        required_params.append("email_config")
        param_types.append(WorkflowParameter.create("email_config", "string"))
    if push_config:
        required_params.append("push_config")
        param_types.append(WorkflowParameter.create("push_config", "string"))

    return {
        "name": f"Morning Delivery - {watchlist.name}",
        "steps": steps,
        "triggers": triggers,
        "supported_goals": ["morning_stock_delivery"],
        "required_parameters": required_params,
        "parameter_types": param_types,
        "automation_domain": "stock_analysis",
        "discovery_tags": ["morning", "delivery", "notification", watchlist.name.lower().replace(" ", "_")],
    }


def create_default_watchlist() -> Watchlist:
    """Create a default watchlist with major US stocks."""
    from app.domain.stock_analysis import WatchlistEntry

    symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
        "JPM", "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD",
        "DIS", "PYPL", "ADBE", "NFLX", "INTC"
    ]

    entries = [WatchlistEntry.create(sym) for sym in symbols]
    return Watchlist.create(name="US Large Cap", entries=entries)


def create_default_email_config() -> EmailConfig:
    """Create default email config from environment variables."""
    import os

    return EmailConfig(
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USERNAME", ""),
        password=os.getenv("SMTP_PASSWORD", ""),
        from_email=os.getenv("SMTP_FROM", ""),
        to_emails=tuple(os.getenv("SMTP_TO", "").split(",")) if os.getenv("SMTP_TO") else (),
        use_tls=os.getenv("SMTP_TLS", "true").lower() == "true",
    )


def create_default_push_config() -> PushConfig:
    """Create default push config from environment variables."""
    import os

    provider = os.getenv("PUSH_PROVIDER", "ntfy")
    return PushConfig(
        provider=provider,
        api_key=os.getenv("PUSH_API_KEY", ""),
        app_id=os.getenv("PUSH_APP_ID"),
        topic=os.getenv("PUSH_TOPIC", "stock_alerts"),
        user_tokens=tuple(os.getenv("PUSH_TOKENS", "").split(",")) if os.getenv("PUSH_TOKENS") else (),
    )
