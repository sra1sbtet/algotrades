from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from loguru import logger

from app.services.quotes import stream_quotes

_INTERVALS = {
    "1s": 1,
    "5s": 5,
    "15s": 15,
    "1m": 60,
    "5m": 300,
}

def _parse_interval(interval: str) -> int:
    return _INTERVALS.get((interval or "1s").lower(), 1)

def _bucket_start(epoch_sec: int, bucket: int) -> int:
    return (epoch_sec // bucket) * bucket

async def stream_bars(symbol: str, interval: str = "1s", fill_gaps: bool = True) -> AsyncIterator[dict]:
    """
    Consume tick stream and yield OHLC bars.
    - Yields an update for the current (open) bar on each tick.
    - When a new bucket starts, yields the finalized previous bar and starts a new one.
    - If fill_gaps=True and multiple buckets pass without ticks, emits flat bars at the previous close.

    Message schema:
    { t: <unix seconds>, symbol: str, o: float, h: float, l: float, c: float }
    """
    bucket = _parse_interval(interval)
    curr_bucket: Optional[int] = None
    o = h = l = c = None
    last_close: Optional[float] = None

    async for tick in stream_quotes(symbol):
        try:
            # Parse tick time
            t_iso = tick.get("t")  # ISO8601 string
            if not t_iso:
                continue
            # Convert to epoch seconds
            dt = datetime.fromisoformat(t_iso.replace("Z", "+00:00"))
            ts = int(dt.timestamp())
            b = _bucket_start(ts, bucket)
            price = float(tick.get("price"))

            if curr_bucket is None:
                curr_bucket = b
                o = h = l = c = price
                last_close = price
                yield {"t": curr_bucket, "symbol": symbol, "o": o, "h": h, "l": l, "c": c}
                continue

            if b == curr_bucket:
                # Update current bar
                c = price
                if price > h: h = price
                if price < l: l = price
                yield {"t": curr_bucket, "symbol": symbol, "o": o, "h": h, "l": l, "c": c}
            else:
                # Emit finalized current bar
                if o is not None:
                    yield {"t": curr_bucket, "symbol": symbol, "o": o, "h": h, "l": l, "c": c}
                    last_close = c
                # Fill gaps with flat bars
                if fill_gaps and last_close is not None:
                    gap = b - curr_bucket
                    while gap > bucket:
                        curr_bucket += bucket
                        yield {"t": curr_bucket, "symbol": symbol, "o": last_close, "h": last_close, "l": last_close, "c": last_close}
                        gap = b - curr_bucket
                # Start new bar
                curr_bucket = b
                o = h = l = c = price
                yield {"t": curr_bucket, "symbol": symbol, "o": o, "h": h, "l": l, "c": c}
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error in stream_bars for %s", symbol)
            await asyncio.sleep(0.1)