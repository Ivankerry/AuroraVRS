from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    MIN_EVENTS_FOR_MODEL: int = 5000
    TWO_TOWER_RETRAIN_INTERVAL_HOURS: float = 6.0

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()
