import asyncio
import random
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from jose import jwt, JWTError
from app.config import settings

router = APIRouter()

async def _auth_ws(token: str):
    try:
        jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

@router.websocket("/ws/quotes")
async def quotes_ws(websocket: WebSocket, symbol: str = Query(...), token: str = Query(...)):
    try:
        await _auth_ws(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()

    price = 100.0 + random.random()
    try:
        while True:
            price += random.uniform(-0.3, 0.3)
            msg = {"t": datetime.utcnow().isoformat() + "Z", "symbol": symbol, "price": round(price, 2)}
            await websocket.send_json(msg)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return