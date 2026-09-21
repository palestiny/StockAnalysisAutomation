from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4


class StockSymbol(str):
    """Validated stock ticker symbol."""

    def __new__(cls, value: str) -> StockSymbol:
        if not isinstance(value, str):
            raise TypeError("StockSymbol must be a string")
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("StockSymbol cannot be empty")
        if not all(c.isalnum() or c in ".-" for c in cleaned):
            raise ValueError(f"Invalid characters in stock symbol: {value}")
        return super().__new__(cls, cleaned)

    @classmethod
    def create(cls, value: str) -> StockSymbol:
        return cls(value)


@dataclass(frozen=True)
class PriceBar:
    """Single session OHLCV data."""

    symbol: StockSymbol
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, StockSymbol):
            raise TypeError("symbol must be a StockSymbol")
        if not isinstance(self.session_date, date):
            raise TypeError("session_date must be a date")
        for field_name in ("open", "high", "low", "close", "adjusted_close"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal")
        if not isinstance(self.volume, int) or self.volume < 0:
            raise ValueError("volume must be a non-negative integer")
        if self.high < self.low:
            raise ValueError("high cannot be less than low")
        if not (self.low <= self.open <= self.high):
            raise ValueError("open must be between low and high")
        if not (self.low <= self.close <= self.high):
            raise ValueError("close must be between low and high")

    @classmethod
    def create(
        cls,
        symbol: str | StockSymbol,
        session_date: date,
        open: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: int,
        adjusted_close: Decimal | None = None,
    ) -> PriceBar:
        return cls(
            symbol=StockSymbol.create(symbol) if isinstance(symbol, str) else symbol,
            session_date=session_date,
            open=open,
            high=high,
            low=low,
            close=close,
            volume=volume,
            adjusted_close=adjusted_close,
        )


@dataclass(frozen=True)
class TechnicalIndicators:
    """Computed technical indicators for a symbol."""

    symbol: StockSymbol
    as_of: date
    rsi_14: Decimal | None = None
    macd_line: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None
    sma_20: Decimal | None = None
    sma_50: Decimal | None = None
    ema_12: Decimal | None = None
    ema_26: Decimal | None = None
    bb_upper: Decimal | None = None
    bb_middle: Decimal | None = None
    bb_lower: Decimal | None = None
    atr_14: Decimal | None = None
    volume_sma_20: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, StockSymbol):
            raise TypeError("symbol must be a StockSymbol")
        if not isinstance(self.as_of, date):
            raise TypeError("as_of must be a date")
        for field_name, value in self.__dict__.items():
            if field_name in ("symbol", "as_of"):
                continue
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal or None")

    @classmethod
    def create(
        cls,
        symbol: str | StockSymbol,
        as_of: date,
        **indicators: Decimal | None,
    ) -> TechnicalIndicators:
        return cls(
            symbol=StockSymbol.create(symbol) if isinstance(symbol, str) else symbol,
            as_of=as_of,
            **indicators,
        )


@dataclass(frozen=True)
class FundamentalMetrics:
    """Fundamental metrics for a symbol."""

    symbol: StockSymbol
    as_of: date
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    roe: Decimal | None = None
    debt_to_equity: Decimal | None = None
    earnings_growth_qoq: Decimal | None = None
    earnings_growth_yoy: Decimal | None = None
    revenue_growth_qoq: Decimal | None = None
    revenue_growth_yoy: Decimal | None = None
    profit_margin: Decimal | None = None
    current_ratio: Decimal | None = None
    market_cap: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, StockSymbol):
            raise TypeError("symbol must be a StockSymbol")
        if not isinstance(self.as_of, date):
            raise TypeError("as_of must be a date")
        for field_name, value in self.__dict__.items():
            if field_name in ("symbol", "as_of"):
                continue
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal or None")

    @classmethod
    def create(
        cls,
        symbol: str | StockSymbol,
        as_of: date,
        **metrics: Decimal | None,
    ) -> FundamentalMetrics:
        return cls(
            symbol=StockSymbol.create(symbol) if isinstance(symbol, str) else symbol,
            as_of=as_of,
            **metrics,
        )


@dataclass(frozen=True)
class MLScore:
    """ML model probability score for next-session positive return."""

    symbol: StockSymbol
    as_of: date
    probability_up: Decimal
    model_version: str
    features_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, StockSymbol):
            raise TypeError("symbol must be a StockSymbol")
        if not isinstance(self.as_of, date):
            raise TypeError("as_of must be a date")
        if not isinstance(self.probability_up, Decimal):
            raise TypeError("probability_up must be a Decimal")
        if not (Decimal("0") <= self.probability_up <= Decimal("1")):
            raise ValueError("probability_up must be between 0 and 1")
        if not self.model_version.strip():
            raise ValueError("model_version cannot be empty")
        if not self.features_hash.strip():
            raise ValueError("features_hash cannot be empty")

    @classmethod
    def create(
        cls,
        symbol: str | StockSymbol,
        as_of: date,
        probability_up: Decimal,
        model_version: str,
        features_hash: str,
    ) -> MLScore:
        return cls(
            symbol=StockSymbol.create(symbol) if isinstance(symbol, str) else symbol,
            as_of=as_of,
            probability_up=probability_up,
            model_version=model_version.strip(),
            features_hash=features_hash.strip(),
        )


class RecommendationAction(Enum):
    BUY = "buy"
    WATCH = "watch"
    AVOID = "avoid"


@dataclass(frozen=True)
class Recommendation:
    """Trading recommendation for a symbol."""

    id: UUID
    symbol: StockSymbol
    action: RecommendationAction
    confidence: Decimal
    entry_price: Decimal | None
    stop_loss: Decimal | None
    target_price: Decimal | None
    rationale: tuple[str, ...]
    technical_score: Decimal | None
    fundamental_score: Decimal | None
    ml_score: MLScore | None
    generated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not isinstance(self.symbol, StockSymbol):
            raise TypeError("symbol must be a StockSymbol")
        if not isinstance(self.action, RecommendationAction):
            raise TypeError("action must be a RecommendationAction")
        if not isinstance(self.confidence, Decimal):
            raise TypeError("confidence must be a Decimal")
        if not (Decimal("0") <= self.confidence <= Decimal("1")):
            raise ValueError("confidence must be between 0 and 1")
        for field_name in ("entry_price", "stop_loss", "target_price"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal or None")
        if not isinstance(self.rationale, tuple) or not all(isinstance(r, str) for r in self.rationale):
            raise TypeError("rationale must be a tuple of strings")
        for field_name in ("technical_score", "fundamental_score"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal or None")
        if self.ml_score is not None and not isinstance(self.ml_score, MLScore):
            raise TypeError("ml_score must be an MLScore or None")
        if not isinstance(self.generated_at, datetime):
            raise TypeError("generated_at must be a datetime")

    @classmethod
    def create(
        cls,
        symbol: str | StockSymbol,
        action: RecommendationAction,
        confidence: Decimal,
        rationale: list[str] | tuple[str, ...],
        entry_price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        target_price: Decimal | None = None,
        technical_score: Decimal | None = None,
        fundamental_score: Decimal | None = None,
        ml_score: MLScore | None = None,
    ) -> Recommendation:
        return cls(
            id=uuid4(),
            symbol=StockSymbol.create(symbol) if isinstance(symbol, str) else symbol,
            action=action,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            rationale=tuple(rationale),
            technical_score=technical_score,
            fundamental_score=fundamental_score,
            ml_score=ml_score,
            generated_at=datetime.utcnow(),
        )


@dataclass(frozen=True)
class WatchlistEntry:
    """Single entry in a watchlist with optional per-symbol parameters."""

    symbol: StockSymbol
    enabled: bool = True
    min_confidence: Decimal = Decimal("0.6")
    custom_params: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, StockSymbol):
            raise TypeError("symbol must be a StockSymbol")
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a bool")
        if not isinstance(self.min_confidence, Decimal):
            raise TypeError("min_confidence must be a Decimal")
        if not (Decimal("0") <= self.min_confidence <= Decimal("1")):
            raise ValueError("min_confidence must be between 0 and 1")
        if self.custom_params is None:
            object.__setattr__(self, "custom_params", {})
        elif not isinstance(self.custom_params, dict):
            raise TypeError("custom_params must be a dict")

    @classmethod
    def create(
        cls,
        symbol: str | StockSymbol,
        enabled: bool = True,
        min_confidence: Decimal = Decimal("0.6"),
        custom_params: dict[str, object] | None = None,
    ) -> WatchlistEntry:
        return cls(
            symbol=StockSymbol.create(symbol) if isinstance(symbol, str) else symbol,
            enabled=enabled,
            min_confidence=min_confidence,
            custom_params=dict(custom_params) if custom_params else {},
        )


@dataclass(frozen=True)
class Watchlist:
    """User-defined watchlist of symbols to analyze."""

    id: UUID
    name: str
    entries: tuple[WatchlistEntry, ...]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not self.name.strip():
            raise ValueError("name cannot be empty")
        if not isinstance(self.entries, tuple) or not all(isinstance(e, WatchlistEntry) for e in self.entries):
            raise TypeError("entries must be a tuple of WatchlistEntry")
        symbols = [e.symbol for e in self.entries]
        if len(set(symbols)) != len(symbols):
            raise ValueError("Watchlist cannot contain duplicate symbols")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if not isinstance(self.updated_at, datetime):
            raise TypeError("updated_at must be a datetime")

    @classmethod
    def create(
        cls,
        name: str,
        entries: list[WatchlistEntry] | tuple[WatchlistEntry, ...] | None = None,
    ) -> Watchlist:
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            name=name.strip(),
            entries=tuple(entries or []),
            created_at=now,
            updated_at=now,
        )

    def enabled_symbols(self) -> tuple[StockSymbol, ...]:
        return tuple(e.symbol for e in self.entries if e.enabled)


@dataclass(frozen=True)
class EmailConfig:
    """Email notification configuration."""

    smtp_host: str
    smtp_port: int
    username: str
    password: str
    from_email: str
    to_emails: tuple[str, ...]
    use_tls: bool = True

    def __post_init__(self) -> None:
        if not self.smtp_host.strip():
            raise ValueError("smtp_host cannot be empty")
        if not isinstance(self.smtp_port, int) or self.smtp_port <= 0:
            raise ValueError("smtp_port must be a positive integer")
        if not self.from_email.strip():
            raise ValueError("from_email cannot be empty")
        if not isinstance(self.to_emails, tuple):
            raise TypeError("to_emails must be a tuple")
        if len(self.to_emails) == 0:
            raise ValueError("to_emails cannot be empty")
        if not all(isinstance(e, str) and e.strip() for e in self.to_emails):
            raise ValueError("to_emails must be non-empty strings")


@dataclass(frozen=True)
class PushConfig:
    """Push notification configuration."""

    provider: str
    api_key: str
    app_id: str | None = None
    topic: str | None = None
    user_tokens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider cannot be empty")
        if not isinstance(self.user_tokens, tuple):
            raise TypeError("user_tokens must be a tuple")
