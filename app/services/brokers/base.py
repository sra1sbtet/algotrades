from typing import Literal
from pydantic import BaseModel, Field

class OrderRequest(BaseModel):
    symbol: str = Field(..., description="User-entered symbol. MT5: exact symbol. Zerodha: 'EXCHANGE:TRADINGSYMBOL' or just TRADINGSYMBOL (defaults to NSE).")
    side: Literal["buy", "sell"]
    qty: float = Field(..., gt=0, description="MT5: lots (can be fractional). Zerodha: integer; will be cast.")
    order_type: Literal["market"] = "market"
    product: str | None = Field(None, description="Zerodha: MIS/NRML. If None, default from settings.")
    tag: str | None = None
    sl: float | None = Field(None, description="Optional stop loss (price). Not used in this minimal example.")
    tp: float | None = Field(None, description="Optional take profit (price). Not used in this minimal example.")

class OrderResponse(BaseModel):
    ok: bool
    broker: str
    order_id: str | None = None
    message: str | None = None

class Broker:
    name = "base"
    def place_order(self, req: OrderRequest) -> OrderResponse:
        raise NotImplementedError