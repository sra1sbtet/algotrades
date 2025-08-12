from fastapi import APIRouter, Depends
from app.auth.security import get_current_user
from app.services.brokers.base import OrderRequest, OrderResponse
from app.services.broker_registry import get_broker

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("", response_model=OrderResponse)
def place_order(req: OrderRequest, user = Depends(get_current_user)):
    broker = get_broker()
    return broker.place_order(req)