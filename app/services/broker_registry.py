from app.config import settings
from app.services.brokers.base import Broker
from app.services.brokers.mt5 import MT5Broker
from app.services.brokers.zerodha import ZerodhaBroker

def get_broker() -> Broker:
    b = (settings.broker or "mt5").lower()
    if b == "mt5":
        return MT5Broker()
    if b == "zerodha":
        return ZerodhaBroker()
    raise ValueError(f"Unsupported broker: {b}")