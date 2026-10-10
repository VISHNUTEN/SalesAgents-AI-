"""Application configuration (Step 7: agent defaults via environment)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SalesAgentsAI"
    ENVIRONMENT: str = "development"
    AGENT_NAME: str = "Anjali"
    AGENT_GENDER: str = "female"
    COMPANY_NAME: str = "Home Credit"
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    STT_PROVIDER: str = "mock"
    TTS_PROVIDER: str = "mock"
    STT_API_KEY: str = ""
    TTS_API_KEY: str = ""

    model_config = {"env_file": "../.env", "extra": "ignore"}


settings = Settings()
