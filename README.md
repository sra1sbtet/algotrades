# AlgoService (MT5 + Zerodha ready)

FastAPI backend with:
- JWT auth (register/login)
- Order API with pluggable brokers: MT5 (live/demo), Zerodha (requires live access token)
- WebSocket for quotes (mock stream for now)
- Simple static HTML page (Lightweight Charts ready)
- SQLite for dev; switch to Postgres in production via DATABASE_URL

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\Activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set BROKER, and the relevant broker credentials
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/static/:
- Register/login
- Connect WS (mock prices)
- Place orders (symbol typed by user)

## Brokers

### MT5 (CFDs/FX)
- Supports demo or live depending on your account.
- Set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER in .env. Optionally MT5_TERMINAL_PATH if auto-init fails.
- Place orders with exact MT5 symbol (e.g., US100Cash, EURUSD, XAUUSD). Quantity is lots (can be fractional). Volume is normalized to min/step.

### Zerodha (F&O / Equity)
- No official paper trading. Use small qty on live or add a local paper engine.
- Generate an access token via KiteConnect login flow and set ZERODHA_ACCESS_TOKEN in .env.
- Symbol format: EXCHANGE:TRADINGSYMBOL (e.g., NFO:NIFTY24AUGFUT) or NSE:RELIANCE. Qty must be int and follow lot sizes for F&O.

## Database

- Dev: SQLite (default).
- Prod: set DATABASE_URL to Postgres (e.g., postgresql+psycopg://user:pass@host:5432/algo). Add Alembic later for schema migrations as the project grows.

## Notes

- WebSocket quotes are mock data now. Replace with real broker/data feed later.
- Trading is risky; comply with your broker’s terms and local regulations.# algotrades
