# Stock Analysis Automation

Daily stock market analysis automation that runs after market close and delivers recommendations before market open via email and push notifications.

## Features

- **Daily Analysis**: Runs after market close (16:00 ET) to analyze price action
- **Technical Indicators**: RSI, MACD, SMA/EMA, Bollinger Bands, ATR, Volume
- **Fundamental Analysis**: P/E, P/B, ROE, Debt/Equity, Growth metrics
- **ML Scoring**: Probability model for next-session positive returns
- **Recommendations**: Buy/Watch/Avoid with entry, stop-loss, target prices
- **Notifications**: Email (SMTP) + Push (ntfy.sh, Firebase, OneSignal)
- **Scheduling**: Trading calendar aware (skips weekends/holidays)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize Configuration

```bash
python -m app.cli_stock_analysis init
```

This creates config files in `~/.automation_os/stock_analysis/`:
- `config.json` - Email and Push notification settings
- `watchlist.json` - Stock symbols to analyze

### 3. Edit Configuration

```bash
# Edit email settings (SMTP)
notepad %USERPROFILE%\.automation_os\stock_analysis\config.json

# Edit watchlist
notepad %USERPROFILE%\.automation_os\stock_analysis\watchlist.json
```

### 4. Run Analysis

```bash
# Run daily analysis now
python -m app.cli_stock_analysis analyze

# Run morning delivery now
python -m app.cli_stock_analysis deliver

# Run scheduler daemon
python -m app.cli_stock_analysis schedule
```

## Configuration

### Email (config.json)
```json
{
  "email": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your_email@gmail.com",
    "password": "your_app_password",
    "from_email": "your_email@gmail.com",
    "to_emails": ["recipient@example.com"],
    "use_tls": true
  }
}
```

### Push Notifications (config.json)
```json
{
  "push": {
    "provider": "ntfy",
    "api_key": "",
    "topic": "my_stock_alerts"
  }
}
```

Supported providers: `ntfy` (simple, no account needed), `firebase`, `onesignal`

### Watchlist (watchlist.json)
```json
{
  "name": "My Portfolio",
  "entries": [
    {"symbol": "AAPL", "enabled": true, "min_confidence": "0.6"},
    {"symbol": "MSFT", "enabled": true, "min_confidence": "0.6"},
    {"symbol": "NVDA", "enabled": true, "min_confidence": "0.6"}
  ]
}
```

## Automation

### Windows Task Scheduler
Create two tasks:
1. **Daily Analysis** - Trigger: Daily at 16:00, Action: `python -m app.cli_stock_analysis analyze`
2. **Morning Delivery** - Trigger: Daily at 08:30, Action: `python -m app.cli_stock_analysis deliver`

### Linux/macOS Cron
```bash
# Daily analysis at 16:00 ET (20:00 UTC)
0 20 * * 1-5 cd /path/to/StockAnalysisAutomation && python -m app.cli_stock_analysis analyze

# Morning delivery at 08:30 ET (12:30 UTC)
30 12 * * 1-5 cd /path/to/StockAnalysisAutomation && python -m app.cli_stock_analysis deliver
```

## Project Structure

```
StockAnalysisAutomation/
├── app/
│   ├── domain/
│   │   ├── stock_analysis.py      # Domain models
│   │   ├── execution.py           # Execution aggregate
│   │   ├── workflow.py            # Workflow aggregate
│   │   ├── execution_event.py     # Event models
│   │   └── repositories.py        # Repository protocols
│   ├── application/
│   │   ├── stock_analysis_workflow.py    # Workflow compositions
│   │   ├── stock_analysis_scheduling.py  # Scheduler with trading calendar
│   │   ├── stock_analysis_config.py      # Configuration management
│   │   ├── capability.py                 # Capability protocol
│   │   ├── capability_result.py          # Result types
│   │   ├── execution_context.py          # Context for capabilities
│   │   ├── scheduling.py                 # Scheduling primitives
│   │   ├── capability_registry.py        # Capability registry
│   │   ├── capability_dispatcher.py      # Capability dispatcher
│   │   ├── condition_evaluator.py        # Condition evaluation
│   │   ├── start_workflow_execution.py   # Start workflow use case
│   │   └── execute_workflow_step.py      # Execute step use case
│   ├── infrastructure/
│   │   ├── capabilities/stock_analysis/
│   │   │   ├── market_data_provider.py   # Yahoo Finance provider
│   │   │   ├── market_data_acquire.py    # Data acquisition capability
│   │   │   ├── technical_analysis.py     # Technical indicators
│   │   │   ├── fundamental_analysis.py   # Fundamental scoring
│   │   │   ├── ml_scoring.py             # ML probability model
│   │   │   ├── recommendation_generation.py  # Recommendation engine
│   │   │   ├── email_notification.py     # Email capability
│   │   │   └── push_notification.py      # Push capability
│   │   └── persistence/in_memory.py      # In-memory repositories
│   └── cli_stock_analysis.py             # CLI entry point
├── requirements.txt
└── README.md
```

## Disclaimer

This is automated analysis for informational purposes only. Not financial advice. Always do your own research before trading.