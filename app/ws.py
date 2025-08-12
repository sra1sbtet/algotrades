import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from jose import jwt, JWTError
from app.config import settings
from app.services.quotes import stream_quotes
from app.services.bars import stream_bars

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

    try:
        async for msg in stream_quotes(symbol):
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        return
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

@router.websocket("/ws/bars")
async def bars_ws(websocket: WebSocket, symbol: str = Query(...), interval: str = Query("1s"), token: str = Query(...)):
    try:
        await _auth_ws(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()

    try:
        async for bar in stream_bars(symbol, interval=interval):
            await websocket.send_json(bar)
    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        return
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)