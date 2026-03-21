#!/usr/bin/env python3
"""
train_lstm.py — Train LSTM price prediction model on historical gold data.

Reads from PostgreSQL price_bars table (seeded by scripts/seed_db.py),
trains a stacked LSTM, and saves the checkpoint to the model registry.

Usage:
    python src/training/train_lstm.py --asset XAU --epochs 50
    python src/training/train_lstm.py --asset XAU --epochs 100 --horizon 10
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("train_lstm")

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    logger.error("PyTorch not installed: pip install torch")
    sys.exit(1)

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    logger.error("psycopg2 not installed: pip install psycopg2-binary")
    sys.exit(1)

from models.lstm_model import LSTMPriceModel
from models.model_registry import ModelMeta, ModelRegistry


# ── Data loading ──────────────────────────────────────────────

def load_price_data(asset: str) -> np.ndarray:
    """Load daily OHLCV bars from Postgres. Returns (N, 5) float32 array."""
    pg = {
        "host":     os.environ.get("POSTGRES_HOST", "localhost"),
        "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname":   os.environ.get("POSTGRES_DB", "financial_dev"),
        "user":     os.environ.get("POSTGRES_USER", "financial"),
        "password": os.environ.get("POSTGRES_PASSWORD", "financial_dev_password"),
    }
    conn = psycopg2.connect(**pg)
    cur = conn.cursor()
    cur.execute("""
        SELECT open, high, low, close, volume
        FROM price_bars
        WHERE asset = %s AND resolution = '1D' AND is_outlier = FALSE
        ORDER BY timestamp ASC
    """, (asset,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        raise ValueError(f"No price data for asset {asset}")
    return np.array(rows, dtype=np.float32)


def make_sequences(
    data: np.ndarray,
    lookback: int,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Create sliding window sequences.

    Returns:
        X: (N, lookback, features)
        y: (N, horizon) — next `horizon` closing prices
    """
    X_list, y_list = [], []
    close_idx = 3  # OHLCV: open=0, high=1, low=2, close=3, vol=4
    for i in range(len(data) - lookback - horizon + 1):
        X_list.append(data[i: i + lookback])
        y_list.append(data[i + lookback: i + lookback + horizon, close_idx])
    return np.array(X_list), np.array(y_list)


def normalize(
    train: np.ndarray, val: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Z-score normalize using training statistics only."""
    mean = train.mean(axis=(0, 1), keepdims=True)
    std  = train.std(axis=(0, 1), keepdims=True) + 1e-8
    return (train - mean) / std, (val - mean) / std, mean.squeeze(), std.squeeze()


# ── Training loop ─────────────────────────────────────────────

def train(
    asset: str,
    lookback: int = 60,
    horizon: int = 5,
    hidden_size: int = 256,
    num_layers: int = 3,
    dropout: float = 0.2,
    epochs: int = 50,
    batch_size: int = 64,
    lr: float = 1e-3,
    val_split: float = 0.15,
    patience: int = 10,
) -> None:
    logger.info("Loading price data for %s ...", asset)
    data = load_price_data(asset)
    logger.info("  %d daily bars loaded", len(data))

    X, y = make_sequences(data, lookback, horizon)
    logger.info("  %d sequences (lookback=%d, horizon=%d)", len(X), lookback, horizon)

    split = int(len(X) * (1 - val_split))
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    X_train_n, X_val_n, _, _ = normalize(X_train, X_val)

    # Normalize targets by the last close in each window
    last_close_train = X_train[:, -1, 3:4]
    last_close_val   = X_val[:, -1, 3:4]
    y_train_n = y_train / (last_close_train + 1e-8)
    y_val_n   = y_val   / (last_close_val   + 1e-8)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Training on: %s", device)

    train_ds = TensorDataset(
        torch.tensor(X_train_n), torch.tensor(y_train_n)
    )
    val_ds = TensorDataset(
        torch.tensor(X_val_n), torch.tensor(y_val_n)
    )
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader   = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    model = LSTMPriceModel(
        input_size=X.shape[2],
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        forecast_horizon=horizon,
    ).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    best_state    = None
    no_improve    = 0

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for X_b, y_b in train_loader:
            X_b, y_b = X_b.to(device), y_b.to(device)
            optimizer.zero_grad()
            preds, _ = model(X_b)
            means     = preds[:, :, 0]
            log_vars  = preds[:, :, 1]
            # Gaussian NLL loss
            loss = (0.5 * log_vars + 0.5 * (y_b - means) ** 2 / (log_vars.exp() + 1e-8)).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += loss.item()
        scheduler.step()

        model.eval()
        val_loss = 0.0
        val_rmse = 0.0
        with torch.no_grad():
            for X_b, y_b in val_loader:
                X_b, y_b = X_b.to(device), y_b.to(device)
                preds, _ = model(X_b)
                means    = preds[:, :, 0]
                log_vars = preds[:, :, 1]
                loss = (0.5 * log_vars + 0.5 * (y_b - means) ** 2 / (log_vars.exp() + 1e-8)).mean()
                val_loss += loss.item()
                val_rmse += ((means - y_b) ** 2).mean().sqrt().item()

        train_loss /= len(train_loader)
        val_loss   /= len(val_loader)
        val_rmse   /= len(val_loader)

        if epoch % 10 == 0 or epoch == 1:
            logger.info(
                "Epoch %3d/%d | train_nll=%.4f | val_nll=%.4f | val_rmse=%.4f | lr=%.2e",
                epoch, epochs, train_loss, val_loss, val_rmse,
                scheduler.get_last_lr()[0],
            )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state    = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve    = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info("Early stopping at epoch %d", epoch)
                break

    # ── Save to registry ──────────────────────────────────────
    registry = ModelRegistry()
    version  = registry.next_version(asset, "lstm")
    meta = ModelMeta(
        asset=asset,
        model_type="lstm",
        version=version,
        trained_at=datetime.now(timezone.utc).isoformat(),
        horizon_days=horizon,
        feature_count=X.shape[2],
        training_rows=len(X_train),
        rmse=val_rmse,
    )
    registry.save_lstm(best_state, meta)
    logger.info("Saved LSTM v%d (val_rmse=%.4f)", version, val_rmse)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train LSTM price model")
    parser.add_argument("--asset",      default="XAU", help="Asset symbol")
    parser.add_argument("--lookback",   type=int, default=60)
    parser.add_argument("--horizon",    type=int, default=5)
    parser.add_argument("--epochs",     type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr",         type=float, default=1e-3)
    parser.add_argument("--patience",   type=int, default=10)
    args = parser.parse_args()

    train(
        asset=args.asset,
        lookback=args.lookback,
        horizon=args.horizon,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        patience=args.patience,
    )


if __name__ == "__main__":
    main()
