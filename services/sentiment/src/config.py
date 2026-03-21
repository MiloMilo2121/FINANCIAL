"""Sentiment service configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentimentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8003)
    log_level: str = Field(default="INFO")
    enable_tracing: bool = Field(default=False)

    # Perplexity
    perplexity_api_key: str = Field(default="")
    perplexity_model: str = Field(default="sonar-pro")

    # Pub/Sub
    pubsub_project_id: str = Field(default="financial-dev")
    pubsub_emulator_host: str | None = Field(default=None)
    pubsub_market_events_subscription: str = Field(default="market-events-sentiment-sub")
    pubsub_sentiment_events_topic: str = Field(default="sentiment-events")

    # Pinecone (semantic deduplication)
    pinecone_api_key: str = Field(default="")
    pinecone_index_name: str = Field(default="financial-embeddings")
    pinecone_semantic_cache_threshold: float = Field(default=0.92)

    # Database
    redis_url: str = Field(default="redis://localhost:6379/0")


settings = SentimentSettings()
