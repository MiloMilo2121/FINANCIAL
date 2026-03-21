"""BERT-based text encoder for financial news and sentiment.

Uses BERT CLS token (768-dim) as the text representation.
The CLS token captures global sentence semantics after attention
over all tokens, making it ideal for document-level classification.

For the cross-modal attention:
  - Text embeddings serve as Query (Q)
  - Price LSTM hidden states serve as Key (K) and Value (V)

This means: text events "query" the price history for relevant
price patterns — geopolitical text events attend to periods of
historical gold volatility, learning when text matters.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer


class BERTTextEncoder(nn.Module):
    """BERT-based encoder producing 768-dim CLS embeddings.

    In production: fine-tuned on financial news corpus.
    By default: uses pre-trained 'bert-base-uncased'.
    """

    def __init__(
        self,
        model_name: str = "bert-base-uncased",
        device: str = "cpu",
        max_length: int = 512,
        freeze_bert: bool = True,
    ) -> None:
        super().__init__()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.bert = AutoModel.from_pretrained(model_name)
        self.device = torch.device(device)
        self.max_length = max_length

        # Freeze BERT weights by default (expensive to fine-tune)
        if freeze_bert:
            for param in self.bert.parameters():
                param.requires_grad = False

        self.bert.to(self.device)

    def encode(self, texts: list[str]) -> torch.Tensor:
        """Encode a batch of texts to CLS embeddings.

        Args:
            texts: List of text strings to encode.

        Returns:
            CLS embeddings: (batch, 768)
        """
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        # Move to device
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.no_grad():
            outputs = self.bert(**encoded)

        # CLS token is the first token's representation
        cls_embeddings = outputs.last_hidden_state[:, 0, :]  # (batch, 768)
        return cls_embeddings

    def encode_numpy(self, texts: list[str]) -> np.ndarray:
        """Convenience method returning numpy array."""
        with torch.no_grad():
            embeddings = self.encode(texts)
        return embeddings.cpu().numpy()

    def forward(self, texts: list[str]) -> torch.Tensor:
        return self.encode(texts)
