from fastapi import APIRouter, HTTPException, status, Depends, Header
from pydantic import BaseModel
from typing import Optional
from app.services.auth import verify_token

router = APIRouter(prefix="/orders", tags=["orders"])

class OrderRequest(BaseModel):
    symbol: str
    side: str  # buy/sell
    qty: float
    product: Optional[str] = None

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    token = authorization.split(" ")[1]
    return verify_token(token)

@router.post("/")
async def place_order(order: OrderRequest, current_user: dict = Depends(get_current_user)):
    # Mock order placement - in production, this would call broker APIs
    order_id = f"ORD_{hash(f'{order.symbol}_{order.side}_{order.qty}')}"
    
    return {
        "order_id": order_id,
        "symbol": order.symbol,
        "side": order.side,
        "qty": order.qty,
        "status": "filled",  # Mock status
        "fill_price": 18000.0 if order.symbol == "US100Cash" else 1.0,
        "message": "Mock order executed successfully"
    }