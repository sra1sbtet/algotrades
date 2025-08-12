# AlgoService (MT5 + Zerodha ready)

FastAPI backend with:
- JWT auth (register/login)
- Order API with pluggable brokers: MT5 (live/demo), Zerodha (requires live access token)
- WebSocket for quotes (real ticks for MT5; Zerodha WS with REST fallback)
- Simple static HTML page (Lightweight Charts ready)
- SQLite for dev; switch to Postgres in production via DATABASE_URL

## Real-time quotes

### MT5 ticks
- /ws/quotes now streams real MT5 ticks using `copy_ticks_from`.
- Message example:
  ```json
  {"t":"2025-08-12T20:10:00Z","symbol":"US100Cash","price":17999.5,"bid":17999.4,"ask":18000.1}
  ```
- Ensure `.env` has MT5 credentials and terminal path if auto-detect fails.

### Zerodha (WebSocket with REST fallback)
- If `BROKER=zerodha`, the service attempts to start KiteTicker WS and subscribe to the requested symbol.
- Symbol format: `EXCHANGE:TRADINGSYMBOL` (e.g., `NFO:NIFTY24AUGFUT`) or `NSE:RELIANCE`.
- On first subscription, instruments for the exchange are loaded to map tradingsymbol to instrument token.
- If KiteTicker isn't available or fails, it falls back to polling `quote` every ~1s to provide LTP.
- Note: Respect Zerodha's rate limits when many clients/symbols are subscribed.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/static/ to try:
- Register/login to get a token
- Connect WS: provide a symbol (e.g., `US100Cash` for MT5, `NSE:RELIANCE` for Zerodha)
- Watch live ticks on the chart

## Notes
- Trading is risky; comply with your broker's terms and local regulations.