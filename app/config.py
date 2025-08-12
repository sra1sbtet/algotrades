from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "AlgoService"
    secret_key: str = Field("change-me-in-.env", alias="SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # SQLite for dev; switch to Postgres in prod by setting DATABASE_URL
    database_url: str = Field("sqlite:///./app.db", alias="DATABASE_URL")

    # Broker selection: "mt5" or "zerodha"
    broker: str = Field("mt5", alias="BROKER")

    # MT5 config (demo/live as per your account)
    mt5_login: int | None = Field(default=None, alias="MT5_LOGIN")
    mt5_password: str | None = Field(default=None, alias="MT5_PASSWORD")
    mt5_server: str | None = Field(default=None, alias="MT5_SERVER")
    mt5_terminal_path: str | None = Field(default=None, alias="MT5_TERMINAL_PATH")
    mt5_deviation: int = Field(10, alias="MT5_DEVIATION")

    # Zerodha (requires live access token)
    zerodha_api_key: str | None = Field(default=None, alias="ZERODHA_API_KEY")
    zerodha_api_secret: str | None = Field(default=None, alias="ZERODHA_API_SECRET")
    zerodha_access_token: str | None = Field(default=None, alias="ZERODHA_ACCESS_TOKEN")
    zerodha_default_product: str = Field("MIS", alias="ZERODHA_DEFAULT_PRODUCT")  # MIS or NRML

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()