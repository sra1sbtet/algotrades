# AlgoService (MT5 + Zerodha ready)

FastAPI backend with:
- JWT auth (register/login)
- Order API with pluggable brokers: MT5 (live/demo), Zerodha (requires live access token)
- WebSocket for quotes (real ticks for MT5; Zerodha WS with REST fallback)
- WebSocket for bars: tick-to-bar aggregation with backfill and persistence
- Simple static HTML page (Lightweight Charts ready)
- SQLite for dev; switch to Postgres in production via DATABASE_URL

## Real-time bars with backfill and persistence

- /ws/bars streams OHLC bars per symbol and interval with multi-subscriber fanout.
- Query params:
  - symbol: required (e.g., `US100Cash`, `NSE:RELIANCE`)
  - interval: one of `1s`, `5s`, `15s`, `1m`, `3m`, `5m`, `15m`, `30m`, `1d`, `1w` (default `1s`)
  - backfill: integer number of recent bars to send as a snapshot on connect (default 150, capped at 5000)
- Messages:
  - Initial snapshot: `{ "type": "snapshot", "bars": [{"t": 1723487400, "o":..., "h":..., "l":..., "c":...}, ...] }`
  - Live updates: `{ "type": "bar", "t": 1723487460, "symbol": "US100Cash", "o":..., "h":..., "l":..., "c":... }`
- Persistence: finalized bars are stored in the `bars` table with unique `(symbol, interval, t)` and reused for backfill.
- Gaps: if there are periods without ticks, flat bars at the last close are emitted to maintain spacing.

### MT5 backfill
- For `BROKER=mt5`, when DB lacks history the server will attempt to backfill via MetaTrader 5 for supported timeframes: `1m, 3m, 5m, 15m, 30m, 1d, 1w`.
- Second-based intervals (`1s`, `5s`, `15s`) are live-only (no historical reconstruction).

### Zerodha backfill
- For `BROKER=zerodha`, backfill is served from the local `bars` table (populated during prior runs). This avoids rate-limit issues. Historical bars from external APIs are not fetched here.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/static/:
- Login to get a token
- Choose Candles, select interval and backfill size, Connect
- You should see snapshot bars plotted, followed by live updates

## Notes
- Trading is risky; comply with your broker's terms and local regulations.
- For production, consider moving DB writes to a background worker and adding migrations (Alembic).