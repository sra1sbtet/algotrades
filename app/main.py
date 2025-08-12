from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import inspect

from app.config import settings
from app.db import Base, engine
from app.models import User  # ensure model is imported so metadata contains it
from app.auth import routes as auth_routes
from app.routers import orders as orders_routes
from app import ws as ws_routes

app = FastAPI(title=settings.app_name)

# CORS - adjust as needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        Base.metadata.create_all(bind=engine)
        logger.info("Initialized database schema")

init_db()

# Routes
app.include_router(auth_routes.router)
app.include_router(orders_routes.router)
app.include_router(ws_routes.router)

# Serve a minimal front page for testing
app.mount("/static", StaticFiles(directory="frontend", html=True), name="static")

@app.get("/healthz")
def health():
    return {"status": "ok", "broker": settings.broker}