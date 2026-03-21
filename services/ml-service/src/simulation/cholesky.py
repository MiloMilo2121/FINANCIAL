"""Cholesky decomposition for generating correlated Brownian motion paths.

In the Heston model, the spot price (S) and variance (v) processes are
correlated via parameter ρ. To simulate them jointly:

1. Generate two independent standard normal samples (Z1, Z2)
2. Apply Cholesky decomposition of correlation matrix C:
   C = [[1, ρ], [ρ, 1]]
   L = cholesky(C) — lower triangular factor

3. Correlated samples: [W1, W2] = L @ [Z1, Z2]

For multi-asset portfolios, the correlation matrix is n×n and
the Cholesky decomposition generalizes naturally.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import cholesky as scipy_cholesky


def build_correlation_matrix(rho: float) -> np.ndarray:
    """Build 2x2 Heston correlation matrix for (spot, variance) processes."""
    return np.array([[1.0, rho], [rho, 1.0]])


def cholesky_factor(corr_matrix: np.ndarray) -> np.ndarray:
    """Compute lower Cholesky factor of a positive definite correlation matrix.

    Uses scipy.linalg.cholesky which is more numerically stable than numpy's.
    Adds a small diagonal regularization (1e-10) to handle near-singular matrices.
    """
    n = corr_matrix.shape[0]
    regularized = corr_matrix + 1e-10 * np.eye(n)
    return scipy_cholesky(regularized, lower=True)


def generate_correlated_normals(
    n_paths: int,
    n_steps: int,
    chol_L: np.ndarray,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Generate correlated standard normal samples using Cholesky decomposition.

    This is the computationally critical inner loop of Monte Carlo simulation.
    Fully vectorized — no Python loops over paths or steps.

    Args:
        n_paths: Number of Monte Carlo paths.
        n_steps: Number of time steps per path.
        chol_L: Lower Cholesky factor (n_factors, n_factors).
        rng: Optional random number generator for reproducibility.

    Returns:
        Correlated normals: (n_factors, n_paths, n_steps)
    """
    if rng is None:
        rng = np.random.default_rng()

    n_factors = chol_L.shape[0]

    # Independent standard normals: (n_factors, n_paths, n_steps)
    Z = rng.standard_normal((n_factors, n_paths, n_steps))

    # Apply Cholesky: W[i] = sum_j L[i,j] * Z[j]
    # Reshape for matrix multiply: (n_paths*n_steps, n_factors) @ L.T
    Z_flat = Z.reshape(n_factors, -1)           # (n_factors, n_paths*n_steps)
    W_flat = chol_L @ Z_flat                    # (n_factors, n_paths*n_steps)
    W = W_flat.reshape(n_factors, n_paths, n_steps)

    return W


def generate_heston_brownians(
    n_paths: int,
    n_steps: int,
    rho: float,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate correlated Brownian increments for the Heston model.

    Returns:
        (dW_S, dW_v): Brownian increments for spot and variance
        Each has shape (n_paths, n_steps).
    """
    corr = build_correlation_matrix(rho)
    L = cholesky_factor(corr)
    W = generate_correlated_normals(n_paths, n_steps, L, rng)
    return W[0], W[1]  # dW_S, dW_v
