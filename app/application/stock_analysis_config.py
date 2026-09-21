from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.stock_analysis import EmailConfig, PushConfig, Watchlist, WatchlistEntry

DEFAULT_CONFIG_DIR = Path.home() / ".automation_os" / "stock_analysis"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_WATCHLIST_FILE = DEFAULT_CONFIG_DIR / "watchlist.json"


class StockAnalysisConfig:
    """Configuration manager for stock analysis automation."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or DEFAULT_CONFIG_DIR
        self._config_file = self._config_dir / "config.json"
        self._watchlist_file = self._config_dir / "watchlist.json"
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def load_email_config(self) -> EmailConfig | None:
        config = self._load_config()
        email_data = config.get("email")
        if not email_data:
            return None
        return EmailConfig(
            smtp_host=email_data.get("smtp_host", "smtp.gmail.com"),
            smtp_port=email_data.get("smtp_port", 587),
            username=email_data.get("username", ""),
            password=email_data.get("password", ""),
            from_email=email_data.get("from_email", ""),
            to_emails=tuple(email_data.get("to_emails", [])),
            use_tls=email_data.get("use_tls", True),
        )

    def load_push_config(self) -> PushConfig | None:
        config = self._load_config()
        push_data = config.get("push")
        if not push_data:
            return None
        return PushConfig(
            provider=push_data.get("provider", "ntfy"),
            api_key=push_data.get("api_key", ""),
            app_id=push_data.get("app_id"),
            topic=push_data.get("topic", "stock_alerts"),
            user_tokens=tuple(push_data.get("user_tokens", [])),
        )

    def load_watchlist(self) -> Watchlist | None:
        if not self._watchlist_file.exists():
            return None

        try:
            with open(self._watchlist_file) as f:
                data = json.load(f)

            entries = []
            for entry_data in data.get("entries", []):
                entries.append(WatchlistEntry.create(
                    symbol=entry_data["symbol"],
                    enabled=entry_data.get("enabled", True),
                    min_confidence=Decimal(str(entry_data.get("min_confidence", "0.6"))),
                    custom_params=entry_data.get("custom_params", {}),
                ))

            watchlist = Watchlist.create(
                name=data.get("name", "Default Watchlist"),
                entries=entries,
            )
            return watchlist
        except Exception:
            return None

    def save_email_config(self, config: EmailConfig) -> None:
        data = self._load_config()
        data["email"] = {
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "username": config.username,
            "password": config.password,
            "from_email": config.from_email,
            "to_emails": list(config.to_emails),
            "use_tls": config.use_tls,
        }
        self._save_config(data)

    def save_push_config(self, config: PushConfig) -> None:
        data = self._load_config()
        data["push"] = {
            "provider": config.provider,
            "api_key": config.api_key,
            "app_id": config.app_id,
            "topic": config.topic,
            "user_tokens": list(config.user_tokens),
        }
        self._save_config(data)

    def save_watchlist(self, watchlist: Watchlist) -> None:
        entries_data = []
        for entry in watchlist.entries:
            entries_data.append({
                "symbol": str(entry.symbol),
                "enabled": entry.enabled,
                "min_confidence": str(entry.min_confidence),
                "custom_params": entry.custom_params,
            })

        data = {
            "name": watchlist.name,
            "entries": entries_data,
        }
        with open(self._watchlist_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load_config(self) -> dict[str, Any]:
        if not self._config_file.exists():
            return {}
        try:
            with open(self._config_file) as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            return {}

    def _save_config(self, data: dict[str, Any]) -> None:
        with open(self._config_file, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def create_example_config(config_dir: Path | None = None) -> None:
        """Create example configuration files."""
        config = StockAnalysisConfig(config_dir)

        email = EmailConfig(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            username="your_email@gmail.com",
            password="your_app_password",
            from_email="your_email@gmail.com",
            to_emails=("recipient@example.com",),
            use_tls=True,
        )
        config.save_email_config(email)

        push = PushConfig(
            provider="ntfy",
            api_key="",
            topic="my_stock_alerts",
        )
        config.save_push_config(push)

        watchlist = Watchlist.create(
            name="My Stocks",
            entries=[
                WatchlistEntry.create("AAPL"),
                WatchlistEntry.create("MSFT"),
                WatchlistEntry.create("GOOGL"),
                WatchlistEntry.create("NVDA"),
                WatchlistEntry.create("TSLA"),
            ],
        )
        config.save_watchlist(watchlist)

        print(f"Example configuration created in {config._config_dir}")
        print("Edit the files to add your credentials and customize watchlist.")
