"""Application configuration (Step 7: agent defaults via environment)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SalesAgentsAI"
    ENVIRONMENT: str = "development"
    AGENT_NAME: str = "Anjali"
    AGENT_GENDER: str = "female"
    COMPANY_NAME: str = "Home Credit"

    model_config = {"env_file": "../.env", "extra": "ignore"}


settings = Settings()
