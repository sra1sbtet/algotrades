from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import auth, orders
from app import ws
import os

app = FastAPI(title="AlgoService", description="Trading service with real-time quotes and bars")

# Include routers
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(ws.router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return {"message": "AlgoService API", "docs": "/docs", "frontend": "/static/"}