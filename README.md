# Financial Projection Platform

Enterprise-grade cloud-native platform for gold and precious metals financial projection, built on Google Cloud Platform.

## Architecture

```
External APIs (Alpha Vantage, MetalpriceAPI, IMF, COMEX, EOSDA, etc.)
        │ polled via APScheduler with Redis rate limiting
        ▼
[ingestion]  →  Pub/Sub "market-events"
        ├────────────────────────────────┐
        ▼                                ▼
[etl / Beam]                    [sentiment / Perplexity]
  → BigQuery + GCS                → Pinecone (semantic cache)
        └──────────┬──────────────────────┘
                   ▼
          [ml-service]
            LSTM-XGBoost hybrid + Heston Monte Carlo
            Cross-Modal Attention Fusion
                   ▼
          [api-gateway]  (JWT, Redis rate limiting, WebSocket)
                   ▼
          [frontend]  React + TradingView Advanced Charts
```

## Services

| Service | Description | Port |
|---|---|---|
| `api-gateway` | Single entry point, JWT auth, WebSocket | 8000 |
| `ingestion` | Data ingestion from 100+ APIs, Redis rate limiting | 8001 |
| `etl` | Apache Beam pipelines (DirectRunner dev / Dataflow prod) | — |
| `ml-service` | LSTM-XGBoost hybrid, Monte Carlo, cross-modal fusion | 8002 |
| `sentiment` | Perplexity Sonar RAG, NLP, GPR event classification | 8003 |
| `frontend` | React/TypeScript, TradingView Advanced Charts | 3000 |

## Quick Start (Local Dev)

### Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+
- `gcloud` CLI (for Pub/Sub emulator)

### Bootstrap

```bash
# Clone and enter repo
cd FINANCIAL

# Copy example env files
cp .env.example .env.dev

# Bootstrap all local services
./scripts/setup_dev.sh

# Start infrastructure (Postgres, Redis, Pub/Sub emulator, fake-GCS)
docker-compose -f docker-compose.dev.yml up -d

# Start all services in dev mode (requires minikube)
skaffold dev --profile=dev
```

### Services individually

```bash
# Install shared library
pip install -e services/shared/

# Run ingestion service
cd services/ingestion && pip install -e . && python src/main.py

# Run ML service
cd services/ml-service && pip install -e . && python src/main.py

# Run sentiment service
cd services/sentiment && pip install -e . && python src/main.py

# Run API gateway
cd services/api-gateway && pip install -e . && python src/main.py

# Run frontend
cd frontend && npm install && npm run dev
```

## Key Technologies

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| ML | PyTorch (LSTM), XGBoost, NumPy/SciPy (Monte Carlo) |
| NLP | HuggingFace Transformers (BERT), Perplexity Sonar API |
| ETL | Apache Beam (DirectRunner → DataflowRunner) |
| Cache | Redis (Token Bucket + Sliding Window rate limiting) |
| Vector DB | Pinecone (real-time), Milvus (backtesting) |
| Message Queue | Google Cloud Pub/Sub |
| Data Warehouse | BigQuery |
| Storage | GCS (raw data staging, model artifacts) |
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Zustand |
| Charts | TradingView Advanced Charts (custom Datafeed API) |
| Infrastructure | GKE, Cloud Run, Terraform, Skaffold |
| CI/CD | Cloud Build, Cloud Deploy |
| Security | Zero-Trust mTLS, GKE Workload Identity, Secret Manager |

## Environment Variables

See `.env.example` for all required environment variables.

Key variables:
- `ALPHA_VANTAGE_API_KEY` — Alpha Vantage API key
- `METALPRICEAPI_KEY` — MetalpriceAPI key
- `METALS_API_KEY` — Metals-API key
- `PERPLEXITY_API_KEY` — Perplexity Sonar API key
- `PINECONE_API_KEY` — Pinecone API key
- `PINECONE_INDEX_NAME` — Pinecone index name
- `REDIS_URL` — Redis connection URL
- `POSTGRES_URL` — PostgreSQL connection URL
- `PUBSUB_PROJECT_ID` — GCP project ID
- `PUBSUB_EMULATOR_HOST` — Set to `localhost:8085` for local dev

## ML Models

### LSTM-XGBoost Hybrid
- LSTM captures temporal dependencies in OHLCV + macro time series
- XGBoost handles non-linear tabular feature interactions
- Ensemble combined via Nelder-Mead optimized weights on validation log-likelihood

### Heston Monte Carlo
- Stochastic volatility model (mean-reverting variance process)
- Cholesky decomposition for correlated spot/variance paths
- 10,000 paths default; vectorized with NumPy for 60x speedup
- Outputs 5/25/50/75/95th percentile bands

### Cross-Modal Attention Fusion
- BERT CLS token (768-dim) encodes news/sentiment text
- LSTM encoder (256-dim) processes price time series
- Scaled dot-product cross-attention: text as Query, prices as Key/Value
- Geopolitical events modulate price predictions dynamically

## Data Sources

| Category | Sources |
|---|---|
| Market Prices | Alpha Vantage, MetalpriceAPI, Metals-API, Marketstack |
| FX Normalization | Open Exchange Rates |
| Institutional | LBMA, COMEX, World Gold Council |
| Macro | IMF WEO, World Bank, OECD, Kenneth French Library |
| Geopolitical | GPR Index (Caldara & Iacoviello, Fed), Perplexity real-time |
| Alternative | EOSDA (satellite), ShipsDNA (maritime), OpenSky (cargo ADS-B) |

## Frontend

Bloomberg Terminal-inspired UI with:
- TradingView Advanced Charts with custom `IDatafeedChartApi`
- LSTM prediction overlay as custom TradingView indicator
- Monte Carlo probability bands (5/25/50/75/95th percentile)
- Geopolitical event marks with Perplexity-generated tooltips
- Sector/metals heatmap for capital flow visualization
- Progressive disclosure UX (cognitive load reduction)
- Dark theme, delta indicators, sparklines

## License

Proprietary
