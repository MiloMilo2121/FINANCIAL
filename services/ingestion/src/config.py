"""Ingestion service configuration via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GCP / Pub/Sub
    pubsub_project_id: str = Field(default="financial-dev")
    pubsub_emulator_host: str | None = Field(default=None)
    pubsub_market_events_topic: str = Field(default="market-events")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_pool_size: int = Field(default=10)

    # GCS
    gcs_bucket_raw: str = Field(default="financial-raw-dev")
    gcs_emulator_host: str | None = Field(default=None)

    # External API keys
    alpha_vantage_api_key: str = Field(default="demo")
    metalpriceapi_key: str = Field(default="")
    metals_api_key: str = Field(default="")
    marketstack_api_key: str = Field(default="")
    open_exchange_rates_app_id: str = Field(default="")
    world_gold_council_api_key: str | None = Field(default=None)
    comex_api_key: str | None = Field(default=None)
    eosda_api_key: str = Field(default="")
    shipsdna_api_key: str = Field(default="")

    # Polling intervals (seconds)
    interval_metals_price: int = Field(default=300)      # 5 minutes
    interval_fx_rates: int = Field(default=3600)          # 1 hour
    interval_macro: int = Field(default=86400)            # Daily
    interval_alternative: int = Field(default=3600)       # 1 hour
    interval_gpr: int = Field(default=3600)               # 1 hour

    # Rate limiting
    alpha_vantage_rate_per_minute: int = Field(default=5)
    metals_api_rate_per_day: int = Field(default=100)

    # Observability
    log_level: str = Field(default="INFO")
    enable_tracing: bool = Field(default=False)


settings = IngestionSettings()
