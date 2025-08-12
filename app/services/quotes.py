import asyncio
import random
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any
from loguru import logger

async def stream_quotes(symbol: str) -> AsyncIterator[Dict[str, Any]]:
    """
    Stream live quotes for a symbol. 
    This is a mock implementation - replace with actual broker integration.
    """
    logger.info(f"Starting quote stream for {symbol}")
    
    # Mock base price
    base_price = 100.0
    if "US100" in symbol.upper():
        base_price = 19500.0
    elif "EURUSD" in symbol.upper():
        base_price = 1.0800
    elif "XAUUSD" in symbol.upper():
        base_price = 2000.0
    elif "NIFTY" in symbol.upper():
        base_price = 25000.0
    elif "RELIANCE" in symbol.upper():
        base_price = 2800.0
    
    current_price = base_price
    
    while True:
        try:
            # Generate realistic price movement
            change_pct = random.uniform(-0.001, 0.001)  # ±0.1% movement
            current_price *= (1 + change_pct)
            
            # Ensure price doesn't drift too far
            if abs(current_price - base_price) / base_price > 0.05:  # 5% max drift
                current_price = base_price * (1 + random.uniform(-0.02, 0.02))
            
            quote = {
                "symbol": symbol,
                "price": round(current_price, 4),
                "t": datetime.now(timezone.utc).isoformat(),
                "bid": round(current_price * 0.9999, 4),
                "ask": round(current_price * 1.0001, 4)
            }
            
            yield quote
            await asyncio.sleep(0.1)  # 10 updates per second
            
        except asyncio.CancelledError:
            logger.info(f"Quote stream cancelled for {symbol}")
            break
        except Exception as e:
            logger.exception(f"Error in quote stream for {symbol}: {e}")
            await asyncio.sleep(1.0)