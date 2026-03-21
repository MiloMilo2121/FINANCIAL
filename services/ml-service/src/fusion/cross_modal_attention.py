"""Cross-Modal Attention module for BERT × LSTM fusion.

Implements scaled dot-product attention between:
  - Query (Q): Text embeddings from BERT (768-dim) — news/geopolitical events
  - Key (K): LSTM hidden states (256-dim) — price time series
  - Value (V): LSTM hidden states (256-dim)

The attention mechanism allows text events to "query" price patterns,
learning which historical price regimes are most relevant to a given
geopolitical context.

If the GPR Index spikes (war threat), the attention scores will amplify
the weight of historical gold patterns during prior geopolitical crises,
producing more context-aware predictions.

Architecture based on "Attention Is All You Need" (Vaswani et al., 2017),
adapted for cross-modal fusion between heterogeneous modalities.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


class CrossModalAttention(nn.Module):
    """Scaled dot-product cross-modal attention.

    Text (Q) attends to price history (K, V).
    Output is a fused representation combining both modalities.

    Args:
        text_dim: Dimension of BERT text embeddings (768).
        price_dim: Dimension of LSTM hidden state (256).
        proj_dim: Common projection dimension for Q, K, V (default 128).
        n_heads: Number of attention heads (multi-head attention).
        dropout: Attention dropout rate.
    """

    def __init__(
        self,
        text_dim: int = 768,
        price_dim: int = 256,
        proj_dim: int = 128,
        n_heads: int = 4,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        assert proj_dim % n_heads == 0, "proj_dim must be divisible by n_heads"

        self.n_heads = n_heads
        self.head_dim = proj_dim // n_heads
        self.scale = math.sqrt(self.head_dim)

        # Project text to Q space
        self.q_proj = nn.Linear(text_dim, proj_dim, bias=False)
        # Project price hidden state to K, V spaces
        self.k_proj = nn.Linear(price_dim, proj_dim, bias=False)
        self.v_proj = nn.Linear(price_dim, proj_dim, bias=False)

        # Output projection back to a combined representation
        self.out_proj = nn.Linear(proj_dim, proj_dim)

        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(proj_dim)

        # Group LASSO sparsity: penalize entire attention heads
        # This forces the model to use fewer heads, improving interpretability
        self.head_gate = nn.Parameter(torch.ones(n_heads))

    def forward(
        self,
        text_embedding: Tensor,   # (batch, text_dim)
        price_hidden: Tensor,     # (batch, price_dim) or (batch, seq, price_dim)
    ) -> tuple[Tensor, Tensor]:
        """Forward pass.

        Returns:
            (fused_output, attention_weights)
            fused_output: (batch, proj_dim)
            attention_weights: (batch, n_heads, 1, seq_len) for visualization
        """
        batch_size = text_embedding.size(0)

        # If price_hidden is 2D (single hidden state), add sequence dimension
        if price_hidden.dim() == 2:
            price_hidden = price_hidden.unsqueeze(1)  # (batch, 1, price_dim)

        seq_len = price_hidden.size(1)

        # Project to Q, K, V
        Q = self.q_proj(text_embedding).unsqueeze(1)  # (batch, 1, proj_dim)
        K = self.k_proj(price_hidden)                  # (batch, seq, proj_dim)
        V = self.v_proj(price_hidden)                  # (batch, seq, proj_dim)

        # Split into heads: (batch, n_heads, seq, head_dim)
        Q = Q.view(batch_size, 1, self.n_heads, self.head_dim).transpose(1, 2)
        K = K.view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        V = V.view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)

        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale  # (batch, heads, 1, seq)
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # Group LASSO: gate attention heads by learned sparsity
        gate = torch.sigmoid(self.head_gate).view(1, self.n_heads, 1, 1)
        attn_weights = attn_weights * gate

        # Aggregate values
        context = torch.matmul(attn_weights, V)  # (batch, heads, 1, head_dim)
        context = context.transpose(1, 2).contiguous()  # (batch, 1, heads, head_dim)
        context = context.view(batch_size, -1)  # (batch, proj_dim)

        # Output projection + residual + layer norm
        output = self.out_proj(context)
        output = self.layer_norm(output + context)

        return output, attn_weights.squeeze(2)  # (batch, proj_dim), (batch, heads, seq)

    def get_sparsity_loss(self) -> Tensor:
        """Group LASSO regularization term for head sparsity.

        Include this in the training loss to encourage the model to use
        fewer attention heads, improving interpretability.
        """
        return torch.sum(torch.abs(self.head_gate))
