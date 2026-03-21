#!/usr/bin/env python3
"""
train_xgboost.py — Train XGBoost residual corrector on gold price data.

XGBoost is trained on LSTM residuals + tabular features (technical indicators,
macro features). Uses TimeSeriesSplit cross-validation.

Usage:
    python src/training/train_xgboost.py --asset XAU
    python src/training/train_xgboost.py --asset XAU --n-estimators 500
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("train_xgboost")

try:
    import psycopg2
except ImportError:
    logger.error("psycopg2 not installed: pip install psycopg2-binary")
    sys.exit(1)

try:
    import xgboost as xgb
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_squared_error, mean_absolute_error
except ImportError:
    logger.error("xgboost/sklearn not installed: pip install xgboost scikit-learn")
    sys.exit(1)

from models.lstm_model import LSTMPriceModel
from models.model_registry import ModelMeta, ModelRegistry


def load_price_data(asset: str) -> np.ndarray:
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
    return np.array(rows, dtype=np.float32)


def build_tabular_features(data: np.ndarray, lookback: int = 60) -> np.ndarray:
    """
    Build tabular features for XGBoost.

    Features per bar:
      - 5-day, 10-day, 20-day, 60-day rolling return
      - 14-day RSI
      - ATR (average true range, 14-day)
      - Close/SMA20 ratio
      - Volume z-score (20-day)
    """
    N = len(data)
    close  = data[:, 3]
    high   = data[:, 1]
    low    = data[:, 2]
    volume = data[:, 4]

    features = np.zeros((N, 8), dtype=np.float32)

    for i in range(lookback, N):
        c = close[:i+1]
        h = high[:i+1]
        l = low[:i+1]
        v = volume[:i+1]

        # Rolling returns
        for j, window in enumerate([5, 10, 20, 60]):
            if i >= window:
                features[i, j] = (c[i] / c[i - window]) - 1.0

        # RSI (14-day)
        if i >= 14:
            deltas = np.diff(c[i-14:i+1])
            gain = deltas[deltas > 0].mean() if (deltas > 0).any() else 1e-8
            loss = -deltas[deltas < 0].mean() if (deltas < 0).any() else 1e-8
            rs = gain / loss
            features[i, 4] = 1.0 - (1.0 / (1.0 + rs))

        # ATR (14-day, normalized)
        if i >= 14:
            tr = np.maximum(h[i-13:i+1] - l[i-13:i+1],
                 np.maximum(np.abs(h[i-13:i+1] - c[i-14:i]),
                            np.abs(l[i-13:i+1] - c[i-14:i])))
            features[i, 5] = tr.mean() / (c[i] + 1e-8)

        # Close/SMA20
        if i >= 20:
            features[i, 6] = c[i] / c[i-20:i+1].mean()

        # Volume z-score (20-day)
        if i >= 20:
            vol_slice = v[i-20:i+1]
            features[i, 7] = (v[i] - vol_slice.mean()) / (vol_slice.std() + 1e-8)

    return features[lookback:]


def train(
    asset: str,
    lookback: int = 60,
    horizon: int = 5,
    n_estimators: int = 300,
    max_depth: int = 5,
    learning_rate: float = 0.05,
    n_splits: int = 5,
) -> None:
    import torch

    logger.info("Loading data for %s ...", asset)
    data = load_price_data(asset)
    logger.info("  %d bars", len(data))

    # ── Get LSTM predictions (residuals target) ───────────────
    registry = ModelRegistry()
    lstm_result = registry.load_lstm(asset)

    if lstm_result is None:
        logger.warning("No LSTM model found for %s — training XGBoost on raw returns", asset)
        # Fall back: predict next-day return from tabular features
        X_tab = build_tabular_features(data, lookback)
        close  = data[lookback:, 3]
        y = np.log(close[1:] / close[:-1])   # next-day log return
        X_tab = X_tab[:-1]  # align
    else:
        lstm_state, lstm_meta = lstm_result
        lstm_model = LSTMPriceModel(
            input_size=5,
            hidden_size=256,
            num_layers=3,
            dropout=0.0,
            forecast_horizon=horizon,
        )
        lstm_model.load_state_dict(lstm_state)
        lstm_model.eval()

        # Build sequences
        sequences = []
        targets   = []
        for i in range(lookback, len(data) - horizon):
            seq = data[i - lookback: i].copy()
            # z-score each feature
            mean = seq.mean(axis=0)
            std  = seq.std(axis=0) + 1e-8
            seq  = (seq - mean) / std
            sequences.append(seq)
            targets.append(data[i + horizon - 1, 3])  # close price at horizon

        X_seq = torch.tensor(np.array(sequences))
        with torch.no_grad():
            preds, _ = lstm_model(X_seq)
            lstm_preds = preds[:, -1, 0].numpy()  # last forecast step, mean

        targets = np.array(targets, dtype=np.float32)
        residuals = targets - lstm_preds

        X_tab = build_tabular_features(data, lookback)[:len(residuals)]
        y = residuals

    # ── TimeSeriesSplit cross-validation ──────────────────────
    logger.info("Training XGBoost with %d-fold TimeSeriesSplit ...", n_splits)

    tscv  = TimeSeriesSplit(n_splits=n_splits)
    rmses, maes = [], []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X_tab)):
        dtrain = xgb.DMatrix(X_tab[train_idx], label=y[train_idx])
        dval   = xgb.DMatrix(X_tab[val_idx],   label=y[val_idx])
        params = {
            "objective":        "reg:squarederror",
            "max_depth":        max_depth,
            "learning_rate":    learning_rate,
            "subsample":        0.8,
            "colsample_bytree": 0.8,
            "alpha":            0.1,
            "lambda":           1.0,
            "seed":             42,
        }
        bst = xgb.train(
            params, dtrain, num_boost_round=n_estimators,
            evals=[(dval, "val")],
            verbose_eval=False,
            early_stopping_rounds=20,
        )
        val_preds = bst.predict(dval)
        rmse = np.sqrt(mean_squared_error(y[val_idx], val_preds))
        mae  = mean_absolute_error(y[val_idx], val_preds)
        rmses.append(rmse)
        maes.append(mae)
        logger.info("  Fold %d: rmse=%.4f mae=%.4f", fold + 1, rmse, mae)

    logger.info("CV RMSE: %.4f ± %.4f", np.mean(rmses), np.std(rmses))

    # ── Full training ─────────────────────────────────────────
    dtrain_full = xgb.DMatrix(X_tab, label=y)
    final_bst = xgb.train(
        params, dtrain_full, num_boost_round=n_estimators,
        verbose_eval=False,
    )

    # ── Save ──────────────────────────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    final_bst.save_model(str(tmp_path))

    version = registry.next_version(asset, "xgboost")
    meta = ModelMeta(
        asset=asset,
        model_type="xgboost",
        version=version,
        trained_at=datetime.now(timezone.utc).isoformat(),
        horizon_days=horizon,
        feature_count=X_tab.shape[1],
        training_rows=len(X_tab),
        rmse=float(np.mean(rmses)),
        mae=float(np.mean(maes)),
    )
    registry.save_xgboost(tmp_path, meta)
    tmp_path.unlink(missing_ok=True)
    logger.info("Saved XGBoost v%d (cv_rmse=%.4f)", version, np.mean(rmses))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train XGBoost residual corrector")
    parser.add_argument("--asset",         default="XAU")
    parser.add_argument("--lookback",      type=int, default=60)
    parser.add_argument("--horizon",       type=int, default=5)
    parser.add_argument("--n-estimators",  type=int, default=300)
    parser.add_argument("--max-depth",     type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    args = parser.parse_args()

    train(
        asset=args.asset,
        lookback=args.lookback,
        horizon=args.horizon,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
    )


if __name__ == "__main__":
    main()
