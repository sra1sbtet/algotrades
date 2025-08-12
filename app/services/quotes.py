from __future__ import annotations
import asyncio
import random
from datetime import datetime, timezone
from typing import AsyncIterator
from loguru import logger

async def stream_quotes(symbol: str) -> AsyncIterator[dict]:
    """
    Mock quote stream for demonstration.
    In production, this would connect to a real data feed.
    """
    logger.info(f"Starting quote stream for {symbol}")
    
    # Start with a base price
    base_price = 18000.0 if symbol == "US100Cash" else 1.0
    current_price = base_price
    
    while True:
        try:
            # Simulate price movement
            change = random.uniform(-0.1, 0.1) * current_price / 100
            current_price += change
            
            # Ensure price doesn't go negative
            current_price = max(current_price, 0.01)
            
            now = datetime.now(timezone.utc)
            tick = {
                "t": now.isoformat(),
                "symbol": symbol,
                "price": round(current_price, 2)
            }
            
            yield tick
            
            # Random delay to simulate real market data
            await asyncio.sleep(random.uniform(0.1, 1.0))
            
        except asyncio.CancelledError:
            logger.info(f"Quote stream cancelled for {symbol}")
            raise
        except Exception as e:
            logger.exception(f"Error in quote stream for {symbol}: {e}")
            await asyncio.sleep(1.0)