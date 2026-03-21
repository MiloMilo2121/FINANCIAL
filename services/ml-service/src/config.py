"""ML service configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8002)
    log_level: str = Field(default="INFO")
    enable_tracing: bool = Field(default=False)

    # Database / Cache
    redis_url: str = Field(default="redis://localhost:6379/0")
    postgres_url: str = Field(default="postgresql+asyncpg://financial:financial_dev_password@localhost:5432/financial")

    # Pinecone
    pinecone_api_key: str = Field(default="")
    pinecone_index_name: str = Field(default="financial-embeddings")
    pinecone_semantic_cache_threshold: float = Field(default=0.92)

    # Milvus
    milvus_host: str = Field(default="localhost")
    milvus_port: int = Field(default=19530)
    milvus_collection_name: str = Field(default="historical_embeddings")

    # LSTM
    lstm_sequence_length: int = Field(default=60)
    lstm_hidden_size: int = Field(default=256)
    lstm_num_layers: int = Field(default=3)
    lstm_dropout: float = Field(default=0.2)
    lstm_forecast_horizon: int = Field(default=5)

    # XGBoost
    xgboost_n_estimators: int = Field(default=500)
    xgboost_max_depth: int = Field(default=6)

    # Monte Carlo
    monte_carlo_paths: int = Field(default=10000)
    monte_carlo_horizon_days: int = Field(default=30)

    # BERT
    bert_model_name: str = Field(default="bert-base-uncased")

    # GCS (model artifacts)
    gcs_bucket_models: str = Field(default="financial-models-dev")
    gcs_emulator_host: str | None = Field(default=None)

    # Routing
    gpr_threshold_for_multimodal: float = Field(default=200.0)


settings = MLSettings()
