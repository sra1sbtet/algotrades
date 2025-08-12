from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    secret_key: str = "your-super-secret-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    database_url: str = "sqlite:///./algotrades.db"
    broker: str = "demo"

    class Config:
        env_file = ".env"

settings = Settings()