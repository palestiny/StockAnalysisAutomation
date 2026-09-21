from __future__ import annotations

from typing import Protocol

from app.application.capability import Capability
from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import PushConfig, Watchlist

PUSH_NOTIFICATION_CAPABILITY_ID = "push_notification"


class PushProvider(Protocol):
    """Protocol for sending push notifications."""

    def send(self, title: str, body: str, data: dict | None = None) -> bool:
        ...


class NtfyPushProvider:
    """Push provider using ntfy.sh (simple HTTP-based push)."""

    def __init__(self, config: PushConfig) -> None:
        self._config = config
        self._topic = config.topic or "stock_alerts"

    def send(self, title: str, body: str, data: dict | None = None) -> bool:
        import requests

        try:
            headers = {
                "Title": title,
                "Priority": "high",
                "Tags": "chart_with_upwards_trend,stock",
            }
            if self._config.api_key:
                headers["Authorization"] = f"Bearer {self._config.api_key}"

            response = requests.post(
                f"https://ntfy.sh/{self._topic}",
                data=body.encode("utf-8"),
                headers=headers,
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False


class FirebasePushProvider:
    """Push provider using Firebase Cloud Messaging."""

    def __init__(self, config: PushConfig) -> None:
        self._config = config

    def send(self, title: str, body: str, data: dict | None = None) -> bool:
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging

            if not firebase_admin._apps:
                cred = credentials.Certificate(self._config.api_key)
                firebase_admin.initialize_app(cred)

            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                tokens=list(self._config.user_tokens),
            )
            response = messaging.send_multicast(message)
            return bool(response.success_count > 0)
        except Exception:
            return False


class OneSignalPushProvider:
    """Push provider using OneSignal."""

    def __init__(self, config: PushConfig) -> None:
        self._config = config

    def send(self, title: str, body: str, data: dict | None = None) -> bool:
        import requests

        try:
            payload = {
                "app_id": self._config.app_id,
                "headings": {"en": title},
                "contents": {"en": body},
                "data": data or {},
                "include_player_ids": list(self._config.user_tokens),
            }
            headers = {
                "Authorization": f"Basic {self._config.api_key}",
                "Content-Type": "application/json",
            }
            response = requests.post(
                "https://onesignal.com/api/v1/notifications",
                json=payload,
                headers=headers,
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False


def create_push_provider(config: PushConfig) -> PushProvider:
    """Factory to create push provider based on config."""
    providers: dict[str, type[PushProvider]] = {
        "ntfy": NtfyPushProvider,
        "firebase": FirebasePushProvider,
        "onesignal": OneSignalPushProvider,
    }
    provider_class = providers.get(config.provider.lower())
    if not provider_class:
        raise ValueError(f"Unknown push provider: {config.provider}")
    return provider_class(config)  # type: ignore[call-arg]


class PushNotificationCapability(Capability):
    """Capability to send push notifications with top recommendations."""

    def __init__(self, provider: PushProvider | None = None) -> None:
        self._provider = provider

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        try:
            recommendations = context.get("recommendations")
            watchlist = context.get("watchlist")
        except KeyError as e:
            return CapabilityResult.failure(f"Missing required context: {e}")

        if not isinstance(recommendations, list):
            return CapabilityResult.failure("recommendations must be a list")
        if not isinstance(watchlist, Watchlist):
            return CapabilityResult.failure("watchlist must be a Watchlist")

        try:
            push_config = context.get("push_config")
        except KeyError:
            return CapabilityResult.failure("push_config is required in execution context")

        if not isinstance(push_config, PushConfig):
            return CapabilityResult.failure("push_config must be a PushConfig instance")

        provider = self._provider or create_push_provider(push_config)

        buy_recs = [r for r in recommendations if r.action.value == "buy"]
        top_buys = buy_recs[:3]

        if top_buys:
            title = f"{len(top_buys)} Buy Signals - {watchlist.name}"
            symbols = ", ".join(str(r.symbol) for r in top_buys)
            body = f"Top picks: {symbols}"
            data = {
                "type": "stock_recommendations",
                "watchlist": watchlist.name,
                "symbols": [str(r.symbol) for r in top_buys],
                "count": len(top_buys),
            }
        else:
            title = f"Daily Analysis Complete - {watchlist.name}"
            body = f"Analyzed {len(recommendations)} symbols. No strong buy signals today."
            data = {"type": "stock_recommendations", "watchlist": watchlist.name}

        success = provider.send(title, body, data)

        if not success:
            return CapabilityResult.failure("Failed to send push notification")

        context.set("push_sent", True)
        return CapabilityResult.success()
