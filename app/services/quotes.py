from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Dict, List, Set
from loguru import logger

from app.config import settings

# -------------------- MT5 TICKS --------------------
try:
    import MetaTrader5 as mt5
except Exception as e:  # pragma: no cover
    mt5 = None
    logger.debug("MetaTrader5 module not available: {}", e)

_mt5_connected = False

def _mt5_connect() -> None:
    global _mt5_connected
    if _mt5_connected:
        return
    if mt5 is None:
        raise RuntimeError("MetaTrader5 module not installed. pip install MetaTrader5")
    ok = mt5.initialize(path=settings.mt5_terminal_path) if settings.mt5_terminal_path else mt5.initialize()
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    if settings.mt5_login and settings.mt5_password and settings.mt5_server:
        if not mt5.login(login=int(settings.mt5_login), password=settings.mt5_password, server=settings.mt5_server):
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
    _mt5_connected = True
    logger.info("MT5 connected for quotes")

def _mt5_ensure_symbol(symbol: str) -> None:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"MT5 symbol not found: {symbol}")
    if not info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Failed to select MT5 symbol: {symbol}")

async def _mt5_stream(symbol: str) -> AsyncIterator[dict]:
    _mt5_connect()
    _mt5_ensure_symbol(symbol)

    from_ts = datetime.now(timezone.utc) - timedelta(seconds=2)
    last_msc = 0
    flags = mt5.COPY_TICKS_ALL

    while True:
        try:
            ticks = mt5.copy_ticks_from(symbol, from_ts, 1000, flags)
            # ticks is a numpy array of structures; iterate in order
            for tk in ticks:
                t_msc = int(tk.time_msc)
                if t_msc <= last_msc:
                    continue
                # Prefer last if available, else mid of bid/ask, else bid/ask individually
                bid = float(getattr(tk, 'bid', 0.0))
                ask = float(getattr(tk, 'ask', 0.0))
                last = float(getattr(tk, 'last', 0.0))
                price = last or (ask and bid and (ask + bid) / 2.0) or ask or bid
                t = datetime.fromtimestamp(int(tk.time), tz=timezone.utc).isoformat().replace('+00:00', 'Z')
                yield {"t": t, "symbol": symbol, "price": round(float(price), 6), "bid": (round(bid, 6) if bid else None), "ask": (round(ask, 6) if ask else None)}
                last_msc = t_msc
            if ticks.size:
                # Advance from_ts to the last tick time to avoid repeats
                last_ts = int(ticks[-1].time)
                from_ts = datetime.fromtimestamp(last_ts, tz=timezone.utc)
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("MT5 stream error for {}", symbol)
            await asyncio.sleep(1.0)

# -------------------- ZERODHA TICKS (WS with REST fallback) --------------------
try:
    from kiteconnect import KiteConnect, KiteTicker  # type: ignore
except Exception as e:  # pragma: no cover
    KiteConnect = None
    KiteTicker = None
    logger.debug("kiteconnect not available: {}", e)

class _ZerodhaWS:
    def __init__(self, api_key: str, access_token: str, loop: asyncio.AbstractEventLoop) -> None:
        if KiteTicker is None or KiteConnect is None:
            raise RuntimeError("kiteconnect not installed. pip install kiteconnect")
        self.loop = loop
        self.kc = KiteConnect(api_key=api_key)
        self.kc.set_access_token(access_token)
        self.kws = KiteTicker(api_key=api_key, access_token=access_token)
        self.token_to_symbol: Dict[int, str] = {}
        self.symbol_to_token: Dict[str, int] = {}
        self.token_subs: Dict[int, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._started = False

        # Register callbacks
        self.kws.on_ticks = self._on_ticks
        self.kws.on_connected = self._on_connected
        self.kws.on_error = self._on_error
        self.kws.on_close = self._on_close

    async def ensure_started(self):
        if self._started:
            return
        self._started = True
        # Start in a separate thread; KiteTicker manages its own reconnects
        asyncio.get_running_loop().run_in_executor(None, self.kws.connect, True)

    async def _ensure_token(self, exchange: str, tradingsymbol: str) -> int:
        key = f"{exchange}:{tradingsymbol}"
        if key in self.symbol_to_token:
            return self.symbol_to_token[key]
        # Build instruments cache for the exchange
        instruments = self.kc.instruments(exchange)
        ts_to_token = {row["tradingsymbol"].upper(): int(row["instrument_token"]) for row in instruments}
        token = ts_to_token.get(tradingsymbol.upper())
        if not token:
            raise RuntimeError(f"Zerodha instrument not found: {exchange}:{tradingsymbol}")
        self.symbol_to_token[key] = token
        self.token_to_symbol[token] = key
        return token

    async def subscribe(self, symbol: str) -> asyncio.Queue:
        # symbol format: EXCHANGE:TRADINGSYMBOL or defaults to NSE
        if ":" in symbol:
            exchange, tsym = symbol.split(":", 1)
            exchange, tsym = exchange.strip().upper(), tsym.strip().upper()
        else:
            exchange, tsym = "NSE", symbol.strip().upper()
        await self.ensure_started()
        token = await self._ensure_token(exchange, tsym)
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        async with self._lock:
            subs = self.token_subs.setdefault(token, set())
            subs.add(q)
            # Subscribe via WS (in WS thread); wrap in executor to avoid blocking loop
            def _subscribe():
                try:
                    self.kws.subscribe([token])
                    self.kws.set_mode(self.kws.MODE_LTP, [token])
                except Exception:
                    logger.exception("Zerodha subscribe failed for token {}", token)
            asyncio.get_running_loop().run_in_executor(None, _subscribe)
        return q

    # KiteTicker callbacks run in WS thread
    def _on_ticks(self, ws, ticks):  # noqa: ANN001
        try:
            for tk in ticks or []:
                token = int(tk.get("instrument_token"))
                ltp = float(tk.get("last_price") or 0.0)
                sym = self.token_to_symbol.get(token, str(token))
                msg = {"t": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), "symbol": sym, "price": ltp}
                queues = list(self.token_subs.get(token, []))
                for q in queues:
                    asyncio.run_coroutine_threadsafe(q.put(msg), self.loop)
        except Exception:
            logger.exception("Error in Zerodha on_ticks")

    def _on_connected(self, ws):  # noqa: ANN001
        logger.info("Zerodha WS connected")

    def _on_error(self, ws, code, reason):  # noqa: ANN001
        logger.error("Zerodha WS error: {} {}", code, reason)

    def _on_close(self, ws, code, reason):  # noqa: ANN001
        logger.warning("Zerodha WS closed: {} {}", code, reason)

_ZWS_SINGLETON: _ZerodhaWS | None = None

async def _zerodha_stream(symbol: str) -> AsyncIterator[dict]:
    if not settings.zerodha_api_key or not settings.zerodha_access_token:
        raise RuntimeError("ZERODHA_API_KEY and ZERODHA_ACCESS_TOKEN must be set for Zerodha streaming")
    global _ZWS_SINGLETON
    loop = asyncio.get_running_loop()
    if _ZWS_SINGLETON is None:
        _ZWS_SINGLETON = _ZerodhaWS(api_key=settings.zerodha_api_key, access_token=settings.zerodha_access_token, loop=loop)
    q = await _ZWS_SINGLETON.subscribe(symbol)
    while True:
        try:
            msg = await q.get()
            yield msg
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Zerodha stream error for {}", symbol)
            await asyncio.sleep(1.0)

# Zerodha REST polling fallback (if WS unavailable)
async def _zerodha_poll(symbol: str) -> AsyncIterator[dict]:
    if KiteConnect is None:
        raise RuntimeError("kiteconnect not installed. pip install kiteconnect")
    if ":" in symbol:
        exchange, tsym = symbol.split(":", 1)
        key = f"{exchange.strip().upper()}:{tsym.strip().upper()}"
    else:
        key = f"NSE:{symbol.strip().upper()}"
    kc = KiteConnect(api_key=settings.zerodha_api_key)
    kc.set_access_token(settings.zerodha_access_token)
    while True:
        try:
            data = kc.quote([key])
            q = data.get(key, {})
            ltp = float(q.get("last_price") or 0.0)
            yield {"t": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), "symbol": key, "price": ltp}
        except Exception:
            logger.exception("Zerodha quote polling failed for {}", key)
        await asyncio.sleep(1.0)

# -------------------- PUBLIC API --------------------
async def stream_quotes(symbol: str) -> AsyncIterator[dict]:
    broker = (settings.broker or "mt5").lower()
    if broker == "mt5":
        async for msg in _mt5_stream(symbol):
            yield msg
        return
    if broker == "zerodha":
        # Try WS first, fallback to REST polling
        try:
            async for msg in _zerodha_stream(symbol):
                yield msg
        except Exception as e:
            logger.warning("Falling back to Zerodha REST polling: {}", e)
            async for msg in _zerodha_poll(symbol):
                yield msg
        return
    # Unknown broker
    raise RuntimeError(f"Unsupported broker for quotes: {broker}")