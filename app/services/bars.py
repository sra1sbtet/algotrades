from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Dict, List, Optional, Set, Tuple
from loguru import logger

from app.config import settings
from app.db import SessionLocal
from app.models import Bar
from app.services.quotes import stream_quotes

# Interval definitions (seconds per bucket) and keys
_INTERVAL_SECONDS: Dict[str, int] = {
    "1s": 1,
    "5s": 5,
    "15s": 15,
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1d": 86400,
    "1w": 604800,
}

_SUPPORTED_FOR_MT5_HISTORY: Set[str] = {"1m", "3m", "5m", "15m", "30m", "1d", "1w"}

# ---------------- Time bucketing helpers ----------------

def _normalize_interval(iv: str | None) -> str:
    if not iv:
        return "1s"
    iv = iv.lower()
    return iv if iv in _INTERVAL_SECONDS else "1s"

def _bucket_start_epoch(dt: datetime, interval_key: str) -> int:
    if interval_key == "1d":
        day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(day.timestamp())
    if interval_key == "1w":
        # ISO week: Monday=0
        monday = (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(monday.timestamp())
    sec = _INTERVAL_SECONDS[interval_key]
    epoch = int(dt.timestamp())
    return (epoch // sec) * sec

# ---------------- Persistence helpers (sync in thread) ----------------

def _db_load_recent(symbol: str, interval: str, limit: int) -> List[Bar]:
    db = SessionLocal()
    try:
        q = (
            db.query(Bar)
            .filter(Bar.symbol == symbol, Bar.interval == interval)
            .order_by(Bar.t.desc())
            .limit(limit)
        )
        rows = list(q)
        return list(reversed(rows))  # ascending time
    finally:
        db.close()

def _db_upsert_bar(symbol: str, interval: str, t: int, o: float, h: float, l: float, c: float) -> None:
    db = SessionLocal()
    try:
        row = db.query(Bar).filter(Bar.symbol == symbol, Bar.interval == interval, Bar.t == t).first()
        if row:
            row.o, row.h, row.l, row.c = float(o), float(h), float(l), float(c)
        else:
            row = Bar(symbol=symbol, interval=interval, t=int(t), o=float(o), h=float(h), l=float(l), c=float(c))
            db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to upsert bar %s %s %s", symbol, interval, t)
    finally:
        db.close()

# ---------------- MT5 backfill (optional) ----------------
try:
    import MetaTrader5 as mt5
except Exception as e:  # pragma: no cover
    mt5 = None
    logger.debug("MetaTrader5 not available for history: {}", e)

def _mt5_connect_once() -> None:
    if mt5 is None:
        raise RuntimeError("MetaTrader5 not installed; cannot backfill")
    # Initialize if not already
    if not mt5.initialize(path=settings.mt5_terminal_path) and mt5.last_error():
        # Try login only if creds provided
        pass
    if settings.mt5_login and settings.mt5_password and settings.mt5_server:
        try:
            mt5.login(login=int(settings.mt5_login), password=settings.mt5_password, server=settings.mt5_server)
        except Exception:
            logger.exception("MT5 login for history failed")

def _mt5_timeframe(interval: str):
    mapping = {
        "1m": getattr(mt5, "TIMEFRAME_M1", None) if mt5 else None,
        "3m": getattr(mt5, "TIMEFRAME_M3", None) if mt5 else None,
        "5m": getattr(mt5, "TIMEFRAME_M5", None) if mt5 else None,
        "15m": getattr(mt5, "TIMEFRAME_M15", None) if mt5 else None,
        "30m": getattr(mt5, "TIMEFRAME_M30", None) if mt5 else None,
        "1d": getattr(mt5, "TIMEFRAME_D1", None) if mt5 else None,
        "1w": getattr(mt5, "TIMEFRAME_W1", None) if mt5 else None,
    }
    return mapping.get(interval)

def _mt5_backfill_sync(symbol: str, interval: str, limit: int) -> List[dict]:
    try:
        _mt5_connect_once()
        tf = _mt5_timeframe(interval)
        if not tf:
            return []
        rates = mt5.copy_rates_from(symbol, tf, datetime.now(timezone.utc), limit)
        out: List[dict] = []
        if rates is None or len(rates) == 0:
            return out
        # rates is numpy array ascending by time; ensure sorted
        for r in rates:
            t = int(r["time"])  # seconds
            o = float(r["open"]) ; h = float(r["high"]) ; l = float(r["low"]) ; c = float(r["close"])    
            out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
        return out
    except Exception:
        logger.exception("MT5 backfill failed for %s %s", symbol, interval)
        return []

async def _load_backfill(symbol: str, interval: str, limit: int) -> List[dict]:
    loop = asyncio.get_running_loop()
    # Load from DB first
    rows: List[Bar] = await loop.run_in_executor(None, _db_load_recent, symbol, interval, limit)
    if rows:
        return [{"t": r.t, "o": r.o, "h": r.h, "l": r.l, "c": r.c} for r in rows]
    # If empty and MT5 supports this interval, try MT5
    if (settings.broker or "mt5").lower() == "mt5" and interval in _SUPPORTED_FOR_MT5_HISTORY:
        hist = await loop.run_in_executor(None, _mt5_backfill_sync, symbol, interval, limit)
        # Persist to DB for reuse
        for b in hist:
            await loop.run_in_executor(None, _db_upsert_bar, symbol, interval, b["t"], b["o"], b["h"], b["l"], b["c"])
        return hist
    return []

# ---------------- Publisher ----------------
@dataclass
class _Sub:
    queue: asyncio.Queue

class BarPublisher:
    def __init__(self, symbol: str, interval: str) -> None:
        self.symbol = symbol
        self.interval = interval
        self.subs: Set[asyncio.Queue] = set()
        self.task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        # Current bar state
        self.curr_t: Optional[int] = None
        self.o: Optional[float] = None
        self.h: Optional[float] = None
        self.l: Optional[float] = None
        self.c: Optional[float] = None

    async def start(self) -> None:
        if self.task and not self.task.done():
            return
        self.task = asyncio.create_task(self._run())

    async def subscribe(self, backfill: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        async with self._lock:
            self.subs.add(q)
            await self.start()
        # Send snapshot
        try:
            hist = await _load_backfill(self.symbol, self.interval, backfill)
            if hist:
                await q.put({"type": "snapshot", "bars": hist})
        except Exception:
            logger.exception("Failed to load backfill for %s %s", self.symbol, self.interval)
        return q

    async def _fanout(self, msg: dict) -> None:
        dead: List[asyncio.Queue] = []
        for q in list(self.subs):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                logger.warning("Dropping subscriber (queue full) for %s %s", self.symbol, self.interval)
                dead.append(q)
        for q in dead:
            self.subs.discard(q)

    async def _persist_final(self, t: int, o: float, h: float, l: float, c: float) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _db_upsert_bar, self.symbol, self.interval, t, o, h, l, c)

    async def _run(self) -> None:
        interval_key = self.interval
        sec = _INTERVAL_SECONDS[interval_key]
        async for tk in stream_quotes(self.symbol):
            try:
                t_iso = tk.get("t")
                if not t_iso:
                    continue
                dt = datetime.fromisoformat(t_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
                bucket_t = _bucket_start_epoch(dt, interval_key)
                price = float(tk.get("price"))
                if self.curr_t is None:
                    self.curr_t = bucket_t
                    self.o = self.h = self.l = self.c = price
                    await self._fanout({"type": "bar", "t": self.curr_t, "symbol": self.symbol, "o": self.o, "h": self.h, "l": self.l, "c": self.c})
                    continue
                if bucket_t == self.curr_t:
                    # Update current bar
                    self.c = price
                    if price > (self.h or price):
                        self.h = price
                    if price < (self.l or price):
                        self.l = price
                    await self._fanout({"type": "bar", "t": self.curr_t, "symbol": self.symbol, "o": self.o, "h": self.h, "l": self.l, "c": self.c})
                else:
                    # Finalize previous bar
                    if None not in (self.curr_t, self.o, self.h, self.l, self.c):
                        await self._persist_final(self.curr_t, self.o, self.h, self.l, self.c)
                    # Fill gaps with flat bars
                    gap = bucket_t - (self.curr_t or bucket_t)
                    while gap > sec and self.c is not None:
                        self.curr_t = (self.curr_t or bucket_t) + sec
                        self.o = self.h = self.l = self.c
                        await self._persist_final(self.curr_t, self.o, self.h, self.l, self.c)
                        await self._fanout({"type": "bar", "t": self.curr_t, "symbol": self.symbol, "o": self.o, "h": self.h, "l": self.l, "c": self.c})
                        gap = bucket_t - (self.curr_t or bucket_t)
                    # Start new
                    self.curr_t = bucket_t
                    self.o = self.h = self.l = self.c = price
                    await self._fanout({"type": "bar", "t": self.curr_t, "symbol": self.symbol, "o": self.o, "h": self.h, "l": self.l, "c": self.c})
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("BarPublisher error for %s %s", self.symbol, self.interval)
                await asyncio.sleep(0.05)

_publishers: Dict[Tuple[str, str], BarPublisher] = {}

async def _get_publisher(symbol: str, interval: str) -> BarPublisher:
    key = (symbol, interval)
    pub = _publishers.get(key)
    if not pub:
        pub = BarPublisher(symbol, interval)
        _publishers[key] = pub
    return pub

async def stream_bars(symbol: str, interval: str = "1s", backfill: int = 150) -> AsyncIterator[dict]:
    interval = _normalize_interval(interval)
    pub = await _get_publisher(symbol, interval)
    q = await pub.subscribe(backfill=max(0, int(backfill)))
    while True:
        try:
            msg = await q.get()
            yield msg
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("stream_bars consumer error for %s %s", symbol, interval)
            await asyncio.sleep(0.1)