# AlgoService (MT5 + Zerodha ready)

FastAPI backend with:
- JWT auth (register/login)
- Order API with pluggable brokers: MT5 (live/demo), Zerodha (requires live access token)
- WebSocket for quotes (real ticks for MT5; Zerodha WS with REST fallback)
- WebSocket for bars: tick-to-bar aggregation (1s/5s/15s/1m/5m) for candles
- Simple static HTML page (Lightweight Charts ready)
- SQLite for dev; switch to Postgres in production via DATABASE_URL

## Real-time quotes and bars

### Ticks
- /ws/quotes streams real ticks with ISO8601 timestamps and price.

### Bars (tick aggregation)
- /ws/bars streams OHLC bars built from ticks.
- Query params:
  - symbol: required (e.g., `US100Cash`, `NSE:RELIANCE`)
  - interval: one of `1s`, `5s`, `15s`, `1m`, `5m` (default `1s`)
- Message example:
  ```json
  {"t": 1723487400, "symbol": "US100Cash", "o": 17999.5, "h": 18001.0, "l": 17998.8, "c": 18000.2}
  ```
- Gaps: If no ticks arrive for a bucket, the server fills gaps with flat bars at the last close to keep candle spacing consistent.

### Frontend
- Toggle chart type between line and candles, choose interval, and connect.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/static/ to try live ticks and candles.