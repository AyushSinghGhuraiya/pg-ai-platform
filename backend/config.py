"""
Application configuration loaded from environment variables via pydantic-settings.
All secrets must live in .env — never hardcode values here.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_anon_key: str = Field(default="", description="Supabase anon/public key")
    supabase_service_key: str = Field(default="", description="Supabase service role key")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")
    upstash_redis_url: str = Field(default="")
    upstash_redis_token: str = Field(default="")

    # ── LLMs ──────────────────────────────────────────────────────────────────
    gemini_api_key: str = Field(default="")
    groq_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    # ── Sarvam AI (Phase 2) ───────────────────────────────────────────────────
    sarvam_api_key: str = Field(default="")

    # ── Vapi (Phase 2) ────────────────────────────────────────────────────────
    vapi_api_key: str = Field(default="")
    vapi_webhook_secret: str = Field(default="")
    vapi_assistant_id: str = Field(default="")

    # ── Exotel (Phase 2) ──────────────────────────────────────────────────────
    exotel_sid: str = Field(default="")
    exotel_token: str = Field(default="")
    exotel_caller_did: str = Field(default="")

    # ── Meta WhatsApp ─────────────────────────────────────────────────────────
    whatsapp_access_token: str = Field(default="")
    whatsapp_phone_number_id: str = Field(default="")
    whatsapp_verify_token: str = Field(default="changeme")
    whatsapp_app_secret: str = Field(default="")

    # ── Observability ─────────────────────────────────────────────────────────
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")
    sentry_dsn: str = Field(default="")

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = Field(default="development")
    app_secret_key: str = Field(default="change_this_to_a_random_32_char_string")
    admin_whatsapp: str = Field(default="")
    default_city: str = Field(default="gurugram")
    default_timezone: str = Field(default="Asia/Kolkata")
    working_hours_start: str = Field(default="09:00")
    working_hours_end: str = Field(default="21:00")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def effective_redis_url(self) -> str:
        """Use Upstash in production, local Redis otherwise."""
        if self.upstash_redis_url:
            return self.upstash_redis_url
        return self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
