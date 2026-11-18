"""Retrieval over the knowledge base.

Two modes (RETRIEVER env var):
  bm25    lexical only. No model download, deterministic, used in CI.
  hybrid  BM25 + dense embeddings fused with reciprocal rank fusion (RRF),
          the same idea as the hybrid retriever in PDF_Assistant, without
          the LangChain dependency.

Both return (Chunk, score) pairs, best first.
"""

import json
import re
from pathlib import Path
from typing import Protocol

from rank_bm25 import BM25Okapi

from app.schemas import Chunk

_TOKEN = re.compile(r"[A-Za-z0-9_\.\-]+")


def tokenize(text: str) -> list[str]:
    # Keep dotted/underscored identifiers intact (e.g. "max_connections", "v2.3.1"):
    # support tickets are full of them and BM25 shines on exact tokens.
    return [t.lower().strip(".-") for t in _TOKEN.findall(text) if t.strip(".-")]


def load_chunks(path: Path) -> list[Chunk]:
    if not Path(path).exists():
        raise FileNotFoundError(
            f"Knowledge base not found at {path}. Run `python -m scripts.ingest_kb` first."
        )
    with open(path, encoding="utf-8") as f:
        return [Chunk(**json.loads(line)) for line in f if line.strip()]


class Retriever(Protocol):
    chunks: list[Chunk]

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]: ...


class BM25Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        # Index title + text so a heading match counts.
        self._bm25 = BM25Okapi([tokenize(f"{c.title} {c.text[-200:]}") for c in chunks])

    def scores(self, query: str) -> list[float]:
        return list(self._bm25.get_scores(tokenize(query)))

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        scores = self.scores(query)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.chunks[i], float(scores[i])) for i in ranked if scores[i] > 0]


class HybridRetriever:
    """BM25 + dense embeddings, fused with reciprocal rank fusion."""

    def __init__(self, chunks: list[Chunk], model_name: str, rrf_k: int = 60, fetch_k: int = 20):
        from sentence_transformers import SentenceTransformer  # optional dependency

        self.chunks = chunks
        self._bm25 = BM25Retriever(chunks)
        self._model = SentenceTransformer(model_name)
        self._emb = self._model.encode(
            [f"{c.title}\n{c.text}" for c in chunks], normalize_embeddings=True
        )
        self._rrf_k = rrf_k
        self._fetch_k = fetch_k

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        bm25_scores = self._bm25.scores(query)
        q = self._model.encode([query], normalize_embeddings=True)[0]
        dense_scores = self._emb @ q

        def ranking(scores) -> list[int]:
            return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[: self._fetch_k]

        fused: dict[int, float] = {}
        for ranked in (ranking(bm25_scores), ranking(dense_scores)):
            for rank, idx in enumerate(ranked):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (self._rrf_k + rank + 1)
        best = sorted(fused, key=fused.get, reverse=True)[:k]
        return [(self.chunks[i], fused[i]) for i in best]


def build_retriever(chunks: list[Chunk], mode: str, embedding_model: str) -> Retriever:
    if mode == "hybrid":
        return HybridRetriever(chunks, embedding_model)
    if mode == "bm25":
        return BM25Retriever(chunks)
    raise ValueError(f"Unknown RETRIEVER mode: {mode!r} (use 'bm25' or 'hybrid')")