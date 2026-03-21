"""API Gateway configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    enable_tracing: bool = Field(default=False)

    # Auth
    jwt_secret_key: str = Field(default="change_this_in_production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60)

    # Redis rate limiting
    redis_url: str = Field(default="redis://localhost:6379/0")
    api_rate_limit_per_minute: int = Field(default=100)

    # Downstream services
    ml_service_url: str = Field(default="http://localhost:8002")
    sentiment_service_url: str = Field(default="http://localhost:8003")
    ingestion_service_url: str = Field(default="http://localhost:8001")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )


settings = GatewaySettings()
