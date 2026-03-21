#!/usr/bin/env bash
# setup_dev.sh — Bootstrap the Financial Projection Platform for local development.
#
# Idempotent: safe to run multiple times.
# Prerequisites: docker, docker compose, python3, psql, redis-cli, curl
#
# Usage:
#   ./scripts/setup_dev.sh              # Full bootstrap
#   ./scripts/setup_dev.sh --skip-deps # Skip docker pull (faster re-runs)
set -euo pipefail

SKIP_DEPS="${1:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.dev"
COMPOSE_FILE="$REPO_ROOT/docker-compose.dev.yml"

# ── Colors ──────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
error()   { echo -e "${RED}[error]${NC} $*"; exit 1; }
section() { echo -e "\n${GREEN}══ $* ══${NC}"; }

# ── 1. Prerequisites ─────────────────────────────────────────
section "Checking prerequisites"

command -v docker      >/dev/null 2>&1 || error "docker not found"
command -v python3     >/dev/null 2>&1 || error "python3 not found"
command -v psql        >/dev/null 2>&1 || warn "psql not found — will use docker exec for DB init"

info "All required tools found"

# ── 2. .env.dev ──────────────────────────────────────────────
section "Environment file"

if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$REPO_ROOT/.env.example" ]]; then
        cp "$REPO_ROOT/.env.example" "$ENV_FILE"
        info "Created $ENV_FILE from .env.example — fill in your API keys"
    else
        warn ".env.example not found, creating minimal .env.dev"
        cat > "$ENV_FILE" <<'EOF'
# Auto-generated minimal dev environment
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=financial_dev
POSTGRES_USER=financial
POSTGRES_PASSWORD=financial_dev_password

REDIS_HOST=localhost
REDIS_PORT=6379

PUBSUB_EMULATOR_HOST=localhost:8085
GCS_EMULATOR_HOST=localhost:4443

GCP_PROJECT_ID=financial-dev
JWT_SECRET_KEY=dev-secret-change-in-production

ML_SERVICE_URL=http://localhost:8001
SENTIMENT_SERVICE_URL=http://localhost:8002

# Fill in real API keys for data ingestion:
ALPHA_VANTAGE_API_KEY=demo
METALPRICEAPI_KEY=
METALS_API_KEY=
MARKETSTACK_API_KEY=
OPEN_EXCHANGE_RATES_APP_ID=
PERPLEXITY_API_KEY=
PINECONE_API_KEY=
EOF
    fi
else
    info "$ENV_FILE already exists — skipping"
fi

# Load env
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# ── 3. Docker Compose ─────────────────────────────────────────
section "Starting infrastructure containers"

if [[ "$SKIP_DEPS" != "--skip-deps" ]]; then
    info "Pulling images (use --skip-deps to skip)..."
    docker compose -f "$COMPOSE_FILE" pull --quiet
fi

docker compose -f "$COMPOSE_FILE" up -d
info "Containers started"

# ── 4. Wait for Postgres ──────────────────────────────────────
section "Waiting for PostgreSQL"

PG_CONTAINER=$(docker compose -f "$COMPOSE_FILE" ps -q postgres 2>/dev/null || echo "")
if [[ -z "$PG_CONTAINER" ]]; then
    PG_CONTAINER=$(docker compose -f "$COMPOSE_FILE" ps -q db 2>/dev/null || echo "")
fi

RETRIES=30
until docker exec "$PG_CONTAINER" pg_isready -U "${POSTGRES_USER:-financial}" -q 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [[ $RETRIES -le 0 ]]; then
        error "PostgreSQL did not become ready in time"
    fi
    echo -n "."
    sleep 2
done
echo ""
info "PostgreSQL is ready"

# ── 5. Initialize database ────────────────────────────────────
section "Initializing database schema"

docker exec -i "$PG_CONTAINER" psql \
    -U "${POSTGRES_USER:-financial}" \
    -d "${POSTGRES_DB:-financial_dev}" \
    < "$REPO_ROOT/scripts/init_db.sql" \
    && info "Schema applied" \
    || warn "Schema may already be applied (idempotent)"

# ── 6. Wait for Redis ─────────────────────────────────────────
section "Waiting for Redis"

REDIS_CONTAINER=$(docker compose -f "$COMPOSE_FILE" ps -q redis 2>/dev/null || echo "")
RETRIES=15
until docker exec "$REDIS_CONTAINER" redis-cli ping 2>/dev/null | grep -q PONG; do
    RETRIES=$((RETRIES - 1))
    if [[ $RETRIES -le 0 ]]; then
        error "Redis did not become ready in time"
    fi
    echo -n "."
    sleep 1
done
echo ""
info "Redis is ready"

# ── 7. Pub/Sub emulator topics ────────────────────────────────
section "Creating Pub/Sub topics and subscriptions"

PUBSUB_EMULATOR_HOST="${PUBSUB_EMULATOR_HOST:-localhost:8085}"
PROJECT_ID="${GCP_PROJECT_ID:-financial-dev}"
PUBSUB_BASE="http://${PUBSUB_EMULATOR_HOST}/v1/projects/${PROJECT_ID}"

RETRIES=20
until curl -sf "$PUBSUB_BASE/topics" >/dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    if [[ $RETRIES -le 0 ]]; then
        error "Pub/Sub emulator did not become ready in time"
    fi
    echo -n "."
    sleep 2
done
echo ""
info "Pub/Sub emulator is ready"

create_topic() {
    local topic="$1"
    curl -sf -X PUT "$PUBSUB_BASE/topics/$topic" >/dev/null \
        && info "  Topic: $topic" \
        || info "  Topic already exists: $topic"
}

create_subscription() {
    local sub="$1"
    local topic="$2"
    curl -sf -X PUT "$PUBSUB_BASE/subscriptions/$sub" \
        -H "Content-Type: application/json" \
        -d "{\"topic\": \"projects/${PROJECT_ID}/topics/${topic}\"}" >/dev/null \
        && info "  Subscription: $sub → $topic" \
        || info "  Subscription already exists: $sub"
}

create_topic "market-events"
create_topic "sentiment-events"
create_subscription "etl-market-events" "market-events"
create_subscription "ml-market-events" "market-events"
create_subscription "sentiment-news-events" "market-events"
create_subscription "api-sentiment-events" "sentiment-events"

# ── 8. Seed historical data ───────────────────────────────────
section "Seeding historical price data"

SEED_FILE="$REPO_ROOT/data/seeds/gold_prices_sample.csv"
if [[ -f "$SEED_FILE" ]]; then
    python3 "$REPO_ROOT/scripts/seed_db.py" \
        && info "Seed data loaded" \
        || warn "Seed script failed — check logs"
else
    warn "Seed file not found at $SEED_FILE — skipping"
fi

# ── 9. Python virtual environments ───────────────────────────
section "Setting up Python virtual environments"

setup_venv() {
    local svc="$1"
    local svc_dir="$REPO_ROOT/services/$svc"
    if [[ -f "$svc_dir/requirements.txt" ]]; then
        info "  Installing $svc dependencies..."
        python3 -m venv "$svc_dir/.venv" --clear 2>/dev/null || true
        "$svc_dir/.venv/bin/pip" install -q --upgrade pip
        "$svc_dir/.venv/bin/pip" install -q -r "$svc_dir/requirements.txt"
        info "  $svc: done"
    fi
}

setup_venv "shared"
setup_venv "ingestion"
setup_venv "etl"
setup_venv "ml-service"
setup_venv "sentiment"
setup_venv "api-gateway"

# ── 10. Frontend ──────────────────────────────────────────────
section "Installing frontend dependencies"

FRONTEND_DIR="$REPO_ROOT/frontend"
if [[ -f "$FRONTEND_DIR/package.json" ]]; then
    if command -v npm >/dev/null 2>&1; then
        cd "$FRONTEND_DIR" && npm install --silent && cd "$REPO_ROOT"
        info "Frontend npm install done"
    else
        warn "npm not found — skipping frontend install"
    fi
fi

# ── Done ──────────────────────────────────────────────────────
section "Bootstrap complete"
echo ""
echo "  Next steps:"
echo "    1. Fill in API keys in $ENV_FILE"
echo "    2. Start services:"
echo "       cd services/ingestion && .venv/bin/python src/main.py"
echo "       cd services/ml-service && .venv/bin/python src/main.py"
echo "       cd services/sentiment  && .venv/bin/python src/main.py"
echo "       cd services/api-gateway && .venv/bin/python src/main.py"
echo "       cd frontend && npm run dev"
echo ""
echo "    Or use Skaffold: skaffold dev --profile=dev"
echo ""
