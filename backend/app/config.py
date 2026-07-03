"""
Central configuration, loaded from environment variables (.env in local dev,
Secret Manager / env vars in Cloud Run).
"""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


class Settings:
    # Mongo
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "wa_agent")

    # Meta / WhatsApp Cloud API
    # Accepts either naming convention: META_* (this project's convention)
    # or WHATSAPP_* (in case your .env uses that instead).
    META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN") or os.getenv("WHATSAPP_TOKEN", "")
    META_PHONE_NUMBER_ID: str = os.getenv("META_PHONE_NUMBER_ID") or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    META_VERIFY_TOKEN: str = os.getenv("META_VERIFY_TOKEN") or os.getenv("WEBHOOK_VERIFY_TOKEN", "changeme_verify_token")
    META_GRAPH_VERSION: str = os.getenv("META_GRAPH_VERSION") or os.getenv("WHATSAPP_API_VERSION", "v20.0")
    META_GRAPH_BASE_URL: str = f"https://graph.facebook.com/{META_GRAPH_VERSION}"

    # LLM
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")  # anthropic | openai
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-5")  # NOTE: ignores ANTHROPIC_MODEL on purpose — see below

    # App
    ENV: str = os.getenv("ENV", "local")
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "*").split(",")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.META_ACCESS_TOKEN:
        import logging

        logging.getLogger("config").warning(
            "META_ACCESS_TOKEN is empty — check that backend/.env exists and "
            "is not being shadowed. Looked for .env at: %s", _ENV_PATH
        )
    return settings