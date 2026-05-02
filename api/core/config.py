from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    MIN_EVENTS_FOR_MODEL: int = 5000
    TWO_TOWER_RETRAIN_INTERVAL_HOURS: float = 6.0
    # CORS Configuration: comma-separated list of allowed origins
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    # Database Connection Pool Configuration
    DB_POOL_SIZE: int = 20
    DB_POOL_OVERFLOW: int = 40

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()
