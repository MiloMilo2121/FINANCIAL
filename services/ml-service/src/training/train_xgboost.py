#!/usr/bin/env python3
"""
train_xgboost.py — Train XGBoost residual corrector using the 175-indicator engine.

XGBoost is trained on LSTM residuals + the full FeaturePipeline feature vector
(175 indicators → top-K via FeatureSelector). Uses TimeSeriesSplit CV.

Usage:
    python src/training/train_xgboost.py --asset XAU
    python src/training/train_xgboost.py --asset XAU --n-estimators 500 --top-k 60
"""

from __future__ import annotations

import argparse
import json
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
from features import FeaturePipeline, FeatureSelector, INDICATOR_REGISTRY


# ── Data loading ──────────────────────────────────────────────────────────────

def _pg_connect():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "financial_dev"),
        user=os.environ.get("POSTGRES_USER", "financial"),
        password=os.environ.get("POSTGRES_PASSWORD", "financial_dev_password"),
    )


def load_price_data(asset: str) -> np.ndarray:
    """Load daily OHLCV bars from Postgres. Returns (N, 5) float32 array."""
    conn = _pg_connect()
    cur  = conn.cursor()
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


def load_external_series(asset: str, n_bars: int) -> dict[str, list[float]]:
    """Load aligned external (macro/alternative) series from Postgres.

    The macro_features table stores daily values for each indicator, aligned
    to the same trading calendar as price_bars.
    Returns dict mapping indicator_name → list of floats (length n_bars),
    forward-filled for missing dates.
    """
    try:
        conn = _pg_connect()
        cur  = conn.cursor()
        cur.execute("""
            SELECT indicator, value_array
            FROM macro_feature_series
            WHERE asset = %s
            ORDER BY indicator
        """, (asset,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result: dict[str, list[float]] = {}
        for indicator, value_json in rows:
            vals = json.loads(value_json) if isinstance(value_json, str) else value_json
            result[indicator] = vals
        return result
    except Exception as exc:
        logger.warning("load_external_series failed: %s — using empty external data", exc)
        return {}


# ── Training ──────────────────────────────────────────────────────────────────

def train(
    asset: str,
    lookback: int = 60,
    horizon: int = 5,
    n_estimators: int = 300,
    max_depth: int = 5,
    learning_rate: float = 0.05,
    n_splits: int = 5,
    top_k: int = 60,
) -> None:
    import torch

    logger.info("Loading data for %s ...", asset)
    data = load_price_data(asset)
    logger.info("  %d bars loaded", len(data))

    # ── Build 175-feature matrix via FeaturePipeline ──────────────────────────
    logger.info("Building 175-indicator feature matrix ...")
    pipeline = FeaturePipeline(INDICATOR_REGISTRY)
    external_series = load_external_series(asset, len(data))
    X_full = pipeline.fit_transform(data, external_series, lookback=lookback)
    feature_names = pipeline.get_feature_names()
    logger.info("  Feature matrix shape: %s  (%d indicators)", X_full.shape, len(feature_names))

    # ── Get LSTM predictions (residuals target) ───────────────────────────────
    registry    = ModelRegistry()
    lstm_result = registry.load_lstm(asset)

    if lstm_result is None:
        logger.warning("No LSTM model for %s — training XGBoost on raw returns", asset)
        close = data[lookback:, 3]
        y     = np.log(close[1:] / close[:-1])   # next-day log return
        X_tab = X_full[:-1]
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

        sequences, targets = [], []
        for i in range(lookback, len(data) - horizon):
            seq  = data[i - lookback: i].copy().astype(np.float32)
            mean = seq.mean(axis=0)
            std  = seq.std(axis=0) + 1e-8
            sequences.append((seq - mean) / std)
            targets.append(data[i + horizon - 1, 3])

        X_seq = torch.tensor(np.array(sequences))
        with torch.no_grad():
            preds, _ = lstm_model(X_seq)
            lstm_preds = preds[:, -1, 0].numpy()

        targets   = np.array(targets, dtype=np.float32)
        residuals = targets - lstm_preds

        X_tab = X_full[: len(residuals)]
        y     = residuals

    assert len(X_tab) == len(y), f"Shape mismatch: X={X_tab.shape}, y={y.shape}"

    # ── Feature Selection: 175 → top_k ───────────────────────────────────────
    logger.info("Selecting top-%d features from %d ...", top_k, X_tab.shape[1])
    selector  = FeatureSelector(top_k=top_k, method="xgboost_importance")
    selector.fit(X_tab, y, feature_names)
    X_sel     = selector.transform(X_tab)
    sel_names = selector.get_selected_features()
    logger.info("  Selected: %s ...", sel_names[:5])

    # ── TimeSeriesSplit cross-validation ──────────────────────────────────────
    logger.info("Training XGBoost with %d-fold TimeSeriesSplit ...", n_splits)
    tscv    = TimeSeriesSplit(n_splits=n_splits)
    rmses, maes = [], []

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

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X_sel)):
        dtrain = xgb.DMatrix(X_sel[train_idx], label=y[train_idx],
                             feature_names=sel_names)
        dval   = xgb.DMatrix(X_sel[val_idx],   label=y[val_idx],
                             feature_names=sel_names)
        bst = xgb.train(
            params, dtrain, num_boost_round=n_estimators,
            evals=[(dval, "val")],
            verbose_eval=False,
            early_stopping_rounds=20,
        )
        val_preds = bst.predict(dval)
        rmse = float(np.sqrt(mean_squared_error(y[val_idx], val_preds)))
        mae  = float(mean_absolute_error(y[val_idx], val_preds))
        rmses.append(rmse)
        maes.append(mae)
        logger.info("  Fold %d: rmse=%.4f mae=%.4f", fold + 1, rmse, mae)

    logger.info("CV RMSE: %.4f ± %.4f", np.mean(rmses), np.std(rmses))

    # ── Full training on all data ─────────────────────────────────────────────
    dtrain_full = xgb.DMatrix(X_sel, label=y, feature_names=sel_names)
    final_bst   = xgb.train(params, dtrain_full, num_boost_round=n_estimators,
                             verbose_eval=False)

    # ── Save model + selector state ───────────────────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    final_bst.save_model(str(tmp_path))

    version = registry.next_version(asset, "xgboost")
    meta = ModelMeta(
        asset         = asset,
        model_type    = "xgboost",
        version       = version,
        trained_at    = datetime.now(timezone.utc).isoformat(),
        horizon_days  = horizon,
        feature_count = len(sel_names),
        training_rows = len(X_sel),
        rmse          = float(np.mean(rmses)),
        mae           = float(np.mean(maes)),
    )
    registry.save_xgboost(tmp_path, meta)
    tmp_path.unlink(missing_ok=True)

    # Persist FeatureSelector alongside model in GCS
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        sel_tmp = Path(f.name)
    selector.save(str(sel_tmp))
    try:
        registry.save_artifact(sel_tmp, f"feature_selector/{asset}/v{version}.json")
    except Exception:
        pass
    sel_tmp.unlink(missing_ok=True)

    logger.info(
        "Saved XGBoost v%d (cv_rmse=%.4f, features=%d selected from %d)",
        version, float(np.mean(rmses)), len(sel_names), len(feature_names),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train XGBoost residual corrector (175-indicator)")
    parser.add_argument("--asset",         default="XAU")
    parser.add_argument("--lookback",      type=int, default=60)
    parser.add_argument("--horizon",       type=int, default=5)
    parser.add_argument("--n-estimators",  type=int, default=300)
    parser.add_argument("--max-depth",     type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--top-k",         type=int, default=60,
                        help="Number of features to select (default 60 of 175)")
    args = parser.parse_args()

    train(
        asset         = args.asset,
        lookback      = args.lookback,
        horizon       = args.horizon,
        n_estimators  = args.n_estimators,
        max_depth     = args.max_depth,
        learning_rate = args.learning_rate,
        top_k         = args.top_k,
    )


if __name__ == "__main__":
    main()
