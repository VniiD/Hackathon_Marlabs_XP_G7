from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@" + "localhost:5432/advisor"
    )
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    whisper_model: str = "tiny"
    open_finance_base_url: str = "https://sandbox.openfinance.example"
    market_news_feed_url: str = "https://www.infomoney.com.br/feed/"
    seed_demo_data: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
