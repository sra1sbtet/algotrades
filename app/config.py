from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application settings
    secret_key: str = "your_secret_key_here_change_in_production"
    jwt_algorithm: str = "HS256"
    database_url: str = "sqlite:///./app.db"
    
    # Broker selection
    broker: Optional[str] = "mt5"
    
    # MT5 Settings
    mt5_login: Optional[str] = None
    mt5_password: Optional[str] = None
    mt5_server: Optional[str] = None
    mt5_terminal_path: Optional[str] = None
    
    # Zerodha Settings
    zerodha_api_key: Optional[str] = None
    zerodha_access_token: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()