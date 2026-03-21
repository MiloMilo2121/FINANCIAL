"""Multimodal fusion: combines LSTM price encoder + BERT text encoder.

Pipeline:
  1. LSTM encodes price time series → 256-dim hidden state
  2. BERT encodes news/sentiment text → 768-dim CLS embedding
  3. CrossModalAttention fuses them → 128-dim fused representation
  4. Fused representation + XGBoost tabular features → final prediction

This is the "Hybrid Fusion" strategy from the architecture spec,
combining the temporal (LSTM) and semantic (BERT) modalities at the
representation level before the final prediction head.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from torch import Tensor

from financial_ml.fusion.text_encoder import BERTTextEncoder
from financial_ml.fusion.cross_modal_attention import CrossModalAttention
from financial_ml.models.lstm_model import LSTMPriceModel


class MultimodalFusion(nn.Module):
    """End-to-end multimodal fusion model.

    Combines LSTM time-series encoder with BERT text encoder via
    cross-modal attention, producing a unified representation for
    the final prediction head.
    """

    def __init__(
        self,
        lstm_model: LSTMPriceModel,
        text_encoder: BERTTextEncoder,
        attention: CrossModalAttention,
        forecast_horizon: int = 5,
    ) -> None:
        super().__init__()
        self.lstm = lstm_model
        self.text_encoder = text_encoder
        self.attention = attention
        self.forecast_horizon = forecast_horizon

        # Final prediction head on top of fused representation
        fused_dim = attention.out_proj.out_features  # proj_dim
        self.prediction_head = nn.Sequential(
            nn.Linear(fused_dim, fused_dim // 2),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(fused_dim // 2, forecast_horizon * 2),  # mean + log_var
        )

    def forward(
        self,
        price_seq: Tensor,       # (batch, seq_len, price_features)
        news_texts: list[str],   # List of news headlines/summaries
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Forward pass through the full multimodal pipeline.

        Returns:
            (predictions, fused_repr, attention_weights)
            predictions: (batch, horizon, 2) — [mean, log_var]
            fused_repr: (batch, proj_dim) — for XGBoost input
            attention_weights: (batch, n_heads, seq) — for visualization
        """
        # LSTM encoding
        _, price_hidden = self.lstm(price_seq)  # (batch, hidden_size)

        # BERT encoding (no gradient through frozen BERT)
        text_emb = self.text_encoder.encode(news_texts)  # (batch, 768)

        # Cross-modal attention fusion
        fused, attn_weights = self.attention(text_emb, price_hidden)  # (batch, proj_dim)

        # Prediction
        raw = self.prediction_head(fused)  # (batch, horizon * 2)
        predictions = raw.view(-1, self.forecast_horizon, 2)

        return predictions, fused, attn_weights

    def get_fused_features_numpy(
        self,
        price_seq: np.ndarray,
        news_texts: list[str],
    ) -> np.ndarray:
        """Extract fused features for XGBoost input (inference only)."""
        with torch.no_grad():
            x = torch.FloatTensor(price_seq)
            _, fused, _ = self.forward(x, news_texts)
        return fused.cpu().numpy()
