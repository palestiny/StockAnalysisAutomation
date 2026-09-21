from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.application.capability import Capability
from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext
from app.domain.stock_analysis import Recommendation, Watchlist, EmailConfig


EMAIL_NOTIFICATION_CAPABILITY_ID = "email_notification"


class EmailProvider(Protocol):
    """Protocol for sending emails."""

    def send(self, subject: str, body: str, to_emails: tuple[str, ...]) -> bool:
        ...


class SMTPEmailProvider:
    """SMTP email provider."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def send(self, subject: str, body: str, to_emails: tuple[str, ...]) -> bool:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            msg = MIMEMultipart()
            msg["From"] = self._config.from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html"))

            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                if self._config.use_tls:
                    server.starttls()
                server.login(self._config.username, self._config.password)
                server.send_message(msg)
            return True
        except Exception:
            return False


class EmailNotificationCapability(Capability):
    """Capability to send email notifications with recommendations."""

    def __init__(self, provider: EmailProvider | None = None) -> None:
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
            email_config = context.get("email_config")
        except KeyError:
            return CapabilityResult.failure("email_config is required in execution context")

        if not isinstance(email_config, EmailConfig):
            return CapabilityResult.failure("email_config must be an EmailConfig instance")

        provider = self._provider or SMTPEmailProvider(email_config)

        subject, body = self._format_email(watchlist.name, recommendations)
        success = provider.send(subject, body, email_config.to_emails)

        if not success:
            return CapabilityResult.failure("Failed to send email notification")

        context.set("email_sent", True)
        return CapabilityResult.success()

    def _format_email(self, watchlist_name: str, recommendations: list[Recommendation]) -> tuple[str, str]:
        from datetime import datetime

        buy_recs = [r for r in recommendations if r.action.value == "buy"]
        watch_recs = [r for r in recommendations if r.action.value == "watch"]
        avoid_recs = [r for r in recommendations if r.action.value == "avoid"]

        subject = f"Daily Stock Recommendations - {watchlist_name} - {datetime.now().strftime('%Y-%m-%d')}"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Daily Stock Analysis - {watchlist_name}</h2>
            <p style="color: #7f8c8d;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            <p style="color: #7f8c8d;">Total analyzed: {len(recommendations)} | Buy: {len(buy_recs)} | Watch: {len(watch_recs)} | Avoid: {len(avoid_recs)}</p>
        """

        if buy_recs:
            html += """
            <h3 style="color: #27ae60;">BUY Recommendations</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <thead>
                    <tr style="background: #27ae60; color: white;">
                        <th style="padding: 10px; text-align: left;">Symbol</th>
                        <th style="padding: 10px; text-align: left;">Confidence</th>
                        <th style="padding: 10px; text-align: left;">Entry</th>
                        <th style="padding: 10px; text-align: left;">Stop Loss</th>
                        <th style="padding: 10px; text-align: left;">Target</th>
                        <th style="padding: 10px; text-align: left;">Rationale</th>
                    </tr>
                </thead>
                <tbody>
            """
            for rec in buy_recs:
                html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px;"><strong>{rec.symbol}</strong></td>
                    <td style="padding: 10px;">{rec.confidence:.1%}</td>
                    <td style="padding: 10px;">${rec.entry_price:.2f}</td>
                    <td style="padding: 10px;">${rec.stop_loss:.2f}</td>
                    <td style="padding: 10px;">${rec.target_price:.2f}</td>
                    <td style="padding: 10px; font-size: 12px;">{' | '.join(rec.rationale)}</td>
                </tr>
                """
            html += "</tbody></table>"

        if watch_recs:
            html += """
            <h3 style="color: #f39c12;">WATCH List</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <thead>
                    <tr style="background: #f39c12; color: white;">
                        <th style="padding: 10px; text-align: left;">Symbol</th>
                        <th style="padding: 10px; text-align: left;">Confidence</th>
                        <th style="padding: 10px; text-align: left;">Rationale</th>
                    </tr>
                </thead>
                <tbody>
            """
            for rec in watch_recs:
                html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px;"><strong>{rec.symbol}</strong></td>
                    <td style="padding: 10px;">{rec.confidence:.1%}</td>
                    <td style="padding: 10px; font-size: 12px;">{' | '.join(rec.rationale)}</td>
                </tr>
                """
            html += "</tbody></table>"

        html += """
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #95a5a6; font-size: 12px;">
                Disclaimer: This is automated analysis for informational purposes only. 
                Not financial advice. Always do your own research before trading.
            </p>
        </body>
        </html>
        """

        return subject, html