"""Heston Stochastic Volatility Model parameters.

The Heston (1993) model describes asset prices where variance is itself
stochastic and mean-reverting, fixing the critical flaw of Black-Scholes
(constant volatility assumption).

dS = μ·S·dt + √v·S·dW₁
dv = κ(θ - v)·dt + σᵥ·√v·dW₂
corr(dW₁, dW₂) = ρ

Parameters:
  S0: Initial spot price
  v0: Initial variance (σ₀²)
  μ: Risk-neutral drift (risk-free rate - convenience yield for gold)
  κ: Mean-reversion speed of variance
  θ: Long-run mean variance (long-run vol²)
  σᵥ: Volatility of variance ("vol of vol")
  ρ: Correlation between spot and variance processes (typically negative)
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class HestonParams:
    """Heston model calibrated parameters for gold (XAU/USD)."""

    # Spot
    S0: float                   # Current spot price (USD/oz)
    # Variance
    v0: float = 0.04            # Initial variance (≈ 20% vol² = 0.04)
    # Drift
    mu: float = 0.05            # Annual risk-neutral drift (risk-free rate)
    # Mean reversion
    kappa: float = 2.0          # Reversion speed — higher = faster mean reversion
    theta: float = 0.04         # Long-run mean variance (≈ 20% long-run vol)
    # Vol of vol
    sigma_v: float = 0.3        # Volatility of variance
    # Correlation
    rho: float = -0.7           # Negative: vol rises when price falls (leverage effect)

    def validate_feller_condition(self) -> bool:
        """Check Feller condition: 2κθ > σᵥ² ensures variance stays positive."""
        feller = 2 * self.kappa * self.theta > self.sigma_v ** 2
        return feller

    @classmethod
    def calibrate_from_history(
        cls,
        prices: np.ndarray,
        dt: float = 1 / 252,
        risk_free_rate: float = 0.05,
    ) -> "HestonParams":
        """Estimate Heston parameters from historical price series.

        Simple method-of-moments estimation:
        - μ from mean log-return
        - v0, θ from realized variance
        - κ, σᵥ, ρ from variance time series autocorrelation

        For production, use maximum likelihood or Kalman filter estimation.
        """
        log_returns = np.diff(np.log(prices))
        realized_var = np.var(log_returns) / dt

        # Variance time series (rolling 21-day)
        window = min(21, len(log_returns) // 5)
        variance_series = np.array([
            np.var(log_returns[max(0, i-window):i]) / dt
            for i in range(window, len(log_returns))
        ])

        # Mean reversion: fit AR(1) to variance series
        if len(variance_series) > 2:
            autocorr = np.corrcoef(variance_series[:-1], variance_series[1:])[0, 1]
            kappa = max(0.1, -np.log(max(0.01, autocorr)) / dt)
        else:
            kappa = 2.0

        # Correlation between returns and variance changes
        if len(variance_series) > 1:
            ret_aligned = log_returns[window:window + len(variance_series) - 1]
            var_changes = np.diff(variance_series)
            min_len = min(len(ret_aligned), len(var_changes))
            if min_len > 2:
                rho = float(np.corrcoef(ret_aligned[:min_len], var_changes[:min_len])[0, 1])
                rho = np.clip(rho, -0.99, 0.99)
            else:
                rho = -0.7
        else:
            rho = -0.7

        return cls(
            S0=float(prices[-1]),
            v0=float(realized_var),
            mu=risk_free_rate,
            kappa=float(kappa),
            theta=float(realized_var),
            sigma_v=0.3,  # Typically hard to estimate from short history
            rho=float(rho),
        )
