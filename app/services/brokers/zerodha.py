from __future__ import annotations
from loguru import logger
from app.services.brokers.base import Broker, OrderRequest, OrderResponse
from app.config import settings

try:
    from kiteconnect import KiteConnect
except Exception as e:  # pragma: no cover
    KiteConnect = None
    logger.warning("kiteconnect module not available: {}", e)

_client: "KiteConnect | None" = None

def _ensure_client() -> "KiteConnect":
    global _client
    if KiteConnect is None:
        raise RuntimeError("kiteconnect module is not installed. pip install kiteconnect")
    if _client is None:
        if not settings.zerodha_api_key:
            raise RuntimeError("ZERODHA_API_KEY not set")
        kc = KiteConnect(api_key=settings.zerodha_api_key)
        if not settings.zerodha_access_token:
            raise RuntimeError("ZERODHA_ACCESS_TOKEN not set. Generate via login flow and set in .env")
        kc.set_access_token(settings.zerodha_access_token)
        _client = kc
    return _client

def _parse_symbol(user_symbol: str) -> tuple[str, str]:
    # Accept "NSE:RELIANCE" or "NFO:NIFTY24AUGFUT" or just "RELIANCE" -> default NSE
    if ":" in user_symbol:
        ex, tsym = user_symbol.split(":", 1)
        return ex.strip().upper(), tsym.strip().upper()
    return "NSE", user_symbol.strip().upper()

class ZerodhaBroker(Broker):
    name = "zerodha"

    def place_order(self, req: OrderRequest) -> OrderResponse:
        kc = _ensure_client()
        side = req.side.lower()
        exchange, tradingsymbol = _parse_symbol(req.symbol)
        product = (req.product or settings.zerodha_default_product).upper()

        try:
            order_id = kc.place_order(
                variety=kc.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                transaction_type="BUY" if side == "buy" else "SELL",
                quantity=int(req.qty),
                product=product,          # MIS intraday or NRML overnight (F&O)
                order_type="MARKET",
                validity="DAY",
                tag=req.tag or "AlgoService",
            )
            return OrderResponse(ok=True, broker=self.name, order_id=str(order_id), message="Order placed")
        except Exception as e:
            logger.exception("Zerodha order failed")
            return OrderResponse(ok=False, broker=self.name, message=str(e))