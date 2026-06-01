from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache


TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9+#/.-]+")


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().replace("ё", "е").split())


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [token for token in TOKEN_RE.findall(normalized) if len(token) > 1]


class EmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class HashingEmbeddingProvider(EmbeddingProvider):
    """Small deterministic local embedding substitute for offline MVP runs."""

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    @lru_cache(maxsize=8192)
    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = tokenize(text)
        if not tokens:
            return vector

        expanded = tokens + [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]
        for token in expanded:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    similarity = sum(a * b for a, b in zip(left, right))
    return max(0.0, min(1.0, (similarity + 1.0) / 2.0))
