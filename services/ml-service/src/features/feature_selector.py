"""FeatureSelector — XGBoost-based feature importance selector.

After training with all 175 indicators, selects the top-K most
important features to reduce model complexity and inference cost.

Usage (training):
    selector = FeatureSelector(top_k=60)
    selector.fit(X_train, y_train, pipeline.get_feature_names())
    X_reduced = selector.transform(X_train)
    selector.save("/models/feature_selector.json")

Usage (inference):
    selector = FeatureSelector.load("/models/feature_selector.json")
    X_reduced = selector.transform(X)
    active_names = selector.get_selected_features()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class FeatureSelector:
    """Select top-K features by XGBoost feature importance (gain).

    Parameters
    ----------
    top_k : int
        Number of features to retain. Default 60 (≈34% of 175).
    method : str
        "xgboost_importance" (default) or "variance" (fallback when
        XGBoost is unavailable).
    """

    def __init__(self, top_k: int = 60, method: str = "xgboost_importance") -> None:
        self.top_k = top_k
        self.method = method
        self._selected_indices: list[int] = []
        self._selected_names: list[str] = []
        self._importance_scores: dict[str, float] = {}
        self._all_names: list[str] = []
        self._is_fitted = False

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
    ) -> "FeatureSelector":
        """Fit selector: compute importance and select top-K features.

        Args:
            X: (N, n_features) training feature matrix.
            y: (N,) target array.
            feature_names: List of feature names, length == n_features.
        Returns:
            self (for chaining)
        """
        assert X.shape[1] == len(feature_names), (
            f"X has {X.shape[1]} features but feature_names has {len(feature_names)}"
        )
        self._all_names = list(feature_names)

        if self.method == "xgboost_importance":
            scores = self._xgb_importance(X, y)
        else:
            scores = self._variance_importance(X, feature_names)

        self._importance_scores = scores

        # Select top-K by score (descending)
        sorted_names = sorted(scores, key=lambda n: scores[n], reverse=True)
        selected = sorted_names[: self.top_k]
        selected_set = set(selected)

        self._selected_indices = [
            i for i, name in enumerate(feature_names) if name in selected_set
        ]
        self._selected_names = [feature_names[i] for i in self._selected_indices]
        self._is_fitted = True

        logger.info(
            "feature_selector.fitted top_k=%d from=%d method=%s",
            len(self._selected_indices), len(feature_names), self.method,
        )
        return self

    def _xgb_importance(
        self, X: np.ndarray, y: np.ndarray
    ) -> dict[str, float]:
        """Compute XGBoost gain-based feature importance."""
        try:
            import xgboost as xgb
            from sklearn.model_selection import TimeSeriesSplit
        except ImportError:
            logger.warning("xgboost not available, falling back to variance selector")
            return self._variance_importance(X, self._all_names)

        params = {
            "objective":        "reg:squarederror",
            "max_depth":        4,
            "learning_rate":    0.1,
            "subsample":        0.8,
            "colsample_bytree": 0.8,
            "n_estimators":     100,
            "seed":             42,
            "verbosity":        0,
        }
        # Quick fit on 80% of data
        n_train = int(0.8 * len(X))
        dtrain  = xgb.DMatrix(X[:n_train], label=y[:n_train])
        bst = xgb.train(
            {k: v for k, v in params.items() if k != "n_estimators"},
            dtrain,
            num_boost_round=params["n_estimators"],
            verbose_eval=False,
        )
        raw_scores = bst.get_score(importance_type="gain")
        # raw_scores keys are "f0", "f1", ... — map back to names
        scores: dict[str, float] = {}
        for fname, score in raw_scores.items():
            idx = int(fname[1:])
            if idx < len(self._all_names):
                scores[self._all_names[idx]] = float(score)
        # Fill zeros for unseen features
        for name in self._all_names:
            if name not in scores:
                scores[name] = 0.0
        return scores

    def _variance_importance(
        self, X: np.ndarray, feature_names: list[str]
    ) -> dict[str, float]:
        """Fallback: rank by variance."""
        variances = X.var(axis=0)
        return {name: float(var) for name, var in zip(feature_names, variances)}

    # ── Inference ─────────────────────────────────────────────────────────────

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Select columns corresponding to top-K features.

        Args:
            X: (..., n_all_features) — can be 1D (175,) or 2D (N, 175).
        Returns:
            (..., top_k) reduced feature array.
        """
        if not self._is_fitted:
            raise RuntimeError("FeatureSelector must be fitted before transform()")
        if X.ndim == 1:
            return X[self._selected_indices]
        return X[:, self._selected_indices]

    def fit_transform(
        self, X: np.ndarray, y: np.ndarray, feature_names: list[str]
    ) -> np.ndarray:
        """Convenience: fit then transform in one call."""
        self.fit(X, y, feature_names)
        return self.transform(X)

    # ── Introspection ─────────────────────────────────────────────────────────

    def get_selected_features(self) -> list[str]:
        """Return names of selected features (in selection order)."""
        return list(self._selected_names)

    def get_importance_scores(self) -> dict[str, float]:
        """Return all importance scores, sorted descending."""
        return dict(sorted(self._importance_scores.items(), key=lambda x: x[1], reverse=True))

    @property
    def n_features_in_(self) -> int:
        return len(self._all_names)

    @property
    def n_features_out_(self) -> int:
        return len(self._selected_indices)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Persist selector state to a JSON file."""
        state = {
            "top_k":             self.top_k,
            "method":            self.method,
            "selected_indices":  self._selected_indices,
            "selected_names":    self._selected_names,
            "all_names":         self._all_names,
            "importance_scores": self._importance_scores,
        }
        Path(path).write_text(json.dumps(state, indent=2))
        logger.info("feature_selector.saved path=%s n_selected=%d", path, len(self._selected_names))

    @classmethod
    def load(cls, path: str | Path) -> "FeatureSelector":
        """Load selector state from JSON file."""
        state = json.loads(Path(path).read_text())
        sel = cls(top_k=state["top_k"], method=state["method"])
        sel._selected_indices  = state["selected_indices"]
        sel._selected_names    = state["selected_names"]
        sel._all_names         = state["all_names"]
        sel._importance_scores = state["importance_scores"]
        sel._is_fitted = True
        logger.info("feature_selector.loaded path=%s n_selected=%d", path, len(sel._selected_names))
        return sel
