"""
Application configuration — all settings loaded from .env via pydantic-settings.
Never hardcode secrets; never import this before the .env file is present.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is one level above this file (backend/)
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    supabase_url: str = Field(default="")
    supabase_anon_key: str = Field(default="")
    supabase_service_key: str = Field(default="")

    # ── Redis (Upstash REST) ──────────────────────────────────────────────────
    upstash_redis_rest_url: str = Field(default="")
    upstash_redis_rest_token: str = Field(default="")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ── LLMs ──────────────────────────────────────────────────────────────────
    gemini_api_key: str = Field(default="")
    groq_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    # ── Phase 2 services ──────────────────────────────────────────────────────
    sarvam_api_key: str = Field(default="")
    vapi_api_key: str = Field(default="")
    vapi_webhook_secret: str = Field(default="")
    vapi_assistant_id: str = Field(default="")
    exotel_sid: str = Field(default="")
    exotel_token: str = Field(default="")
    exotel_caller_did: str = Field(default="")

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    whatsapp_access_token: str = Field(default="")
    whatsapp_phone_number_id: str = Field(default="")
    whatsapp_waba_id: str = Field(default="")
    whatsapp_verify_token: str = Field(default="changeme")
    whatsapp_app_secret: str = Field(default="")

    # ── Observability ─────────────────────────────────────────────────────────
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")
    sentry_dsn: str = Field(default="")

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = Field(default="development")
    app_secret_key: str = Field(default="change_me_32chars")
    admin_whatsapp: str = Field(default="")
    default_city: str = Field(default="gurugram")
    default_timezone: str = Field(default="Asia/Kolkata")
    working_hours_start: str = Field(default="09:00")
    working_hours_end: str = Field(default="21:00")
    default_tenant_id: str = Field(default="")
    test_whatsapp_number: str = Field(default="")

    # ── Computed helpers ──────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def db_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def redis_configured(self) -> bool:
        return bool(self.upstash_redis_rest_url and self.upstash_redis_rest_token)

    @property
    def llm_configured(self) -> bool:
        return bool(self.gemini_api_key or self.groq_api_key or self.openai_api_key)

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @field_validator("supabase_url", mode="before")
    @classmethod
    def _validate_supabase_url(cls, v: str) -> str:
        if v and not v.startswith("https://"):
            raise ValueError("SUPABASE_URL must start with https://")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
