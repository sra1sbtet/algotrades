from pydantic import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "AlgoService"
    secret_key: str = "your-secret-key-here-change-in-production"
    jwt_algorithm: str = "HS256"
    database_url: str = "sqlite:///./algo.db"
    
    # Broker settings
    broker: str = "mt5"
    
    # MT5 settings
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_terminal_path: str = ""
    
    # Zerodha settings
    zerodha_access_token: str = ""
    zerodha_api_key: str = ""
    zerodha_api_secret: str = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()