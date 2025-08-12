from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.ws import router as ws_router
from app.config import settings

app = FastAPI(title="AlgoTrades", description="Real-time trading quotes and orders API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WebSocket router
app.include_router(ws_router)

@app.get("/")
def read_root():
    return {"message": "AlgoTrades API", "broker": settings.broker}

@app.get("/health")
def health_check():
    return {"status": "healthy", "broker": settings.broker}