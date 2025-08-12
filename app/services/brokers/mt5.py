from __future__ import annotations
from loguru import logger
from app.services.brokers.base import Broker, OrderRequest, OrderResponse
from app.config import settings

try:
    import MetaTrader5 as mt5
except Exception as e:  # pragma: no cover
    mt5 = None
    logger.warning("MetaTrader5 module not available: {}", e)

_connected = False

def _ensure_connected() -> None:
    global _connected
    if _connected:
        return
    if mt5 is None:
        raise RuntimeError("MetaTrader5 module is not installed. pip install MetaTrader5")
    # Initialize terminal
    ok = mt5.initialize(path=settings.mt5_terminal_path) if settings.mt5_terminal_path else mt5.initialize()
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    # Login if creds provided (for multi-accounts)
    if settings.mt5_login and settings.mt5_password and settings.mt5_server:
        if not mt5.login(login=int(settings.mt5_login), password=settings.mt5_password, server=settings.mt5_server):
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
    _connected = True
    logger.info("Connected to MT5")

def _ensure_symbol(symbol: str) -> None:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Symbol not found: {symbol}")
    if not info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Failed to select symbol: {symbol}")

def _normalize_volume(symbol: str, lots: float) -> float:
    info = mt5.symbol_info(symbol)
    if info is None:
        return lots
    vol_min = getattr(info, "volume_min", 0.01) or 0.01
    vol_step = getattr(info, "volume_step", 0.01) or 0.01
    vol_max = getattr(info, "volume_max", 100.0) or 100.0
    lots = max(vol_min, min(vol_max, lots))
    # align to step
    steps = round((lots - vol_min) / vol_step)
    return round(vol_min + steps * vol_step, 2)

class MT5Broker(Broker):
    name = "mt5"

    def place_order(self, req: OrderRequest) -> OrderResponse:
        _ensure_connected()
        _ensure_symbol(req.symbol)

        side = req.side.lower()
        tick = mt5.symbol_info_tick(req.symbol)
        if tick is None:
            return OrderResponse(ok=False, broker=self.name, message="No tick data")

        price = tick.ask if side == "buy" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        lots = _normalize_volume(req.symbol, float(req.qty))

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": lots,
            "type": order_type,
            "price": price,
            "deviation": int(settings.mt5_deviation),
            "type_filling": mt5.ORDER_FILLING_FOK,  # use IOC if required by your broker
            "type_time": mt5.ORDER_TIME_GTC,
            "magic": 20250812,
            "comment": req.tag or "AlgoService",
        }

        logger.info(f"MT5 order_send: {request}")
        result = mt5.order_send(request)
        if result is None:
            return OrderResponse(ok=False, broker=self.name, message=f"order_send returned None: {mt5.last_error()}")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResponse(ok=False, broker=self.name, message=f"MT5 error {result.retcode}: {result.comment}")
        return OrderResponse(ok=True, broker=self.name, order_id=str(result.order), message="Filled")