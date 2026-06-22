"""Tool: vector store for RAG grounding.

Embeds the company **playbook** (standard clause positions) and **policy**
(compliance rules) and retrieves the most relevant passages for a clause. This
is genuine retrieval: the analysis and compliance agents ground their decisions
in the actual playbook/policy text rather than free-associating.

Two backends behind one interface:
  * **live**  — OpenAI embeddings (``text-embedding-3-small``) + cosine.
  * **mock**  — deterministic TF-IDF bag-of-words + cosine (no keys, no network).

Markdown is chunked on ``##`` headings, so each chunk maps to a clause topic and
gets a stable citation id like ``playbook.md#limitation_of_liability``.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from llm import is_live

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _slug(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", heading.strip().lower()).strip("_")


def _chunk_markdown(path: Path, filename: str) -> List[Tuple[str, str]]:
    """Split a markdown file into (citation_source, text) chunks by ## heading."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    chunks: List[Tuple[str, str]] = []
    cur_head = "intro"
    cur: List[str] = []

    def flush():
        body = "\n".join(cur).strip()
        if body:
            chunks.append((f"{filename}#{_slug(cur_head)}", body))

    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            flush()
            cur_head = m.group(1).strip()
            cur = [line]
        else:
            cur.append(line)
    flush()
    return chunks


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class VectorStore:
    """In-memory store with cosine retrieval over playbook + policy chunks."""

    def __init__(self) -> None:
        self.sources: List[str] = []
        self.texts: List[str] = []
        self.matrix: Optional[np.ndarray] = None
        self.mode = "live" if is_live() else "mock"
        # mock (tf-idf) state
        self._vocab: dict = {}
        self._idf: Optional[np.ndarray] = None

    # ----- ingest -----
    def add_markdown(self, filename: str) -> None:
        for source, text in _chunk_markdown(DATA_DIR / filename, filename):
            self.sources.append(source)
            self.texts.append(text)

    def build(self) -> None:
        if not self.texts:
            return
        if self.mode == "live":
            try:
                self.matrix = self._embed_live(self.texts)
                return
            except Exception as exc:
                # Degrade gracefully: a live-embedding failure (bad key, no
                # quota, network) must not crash retrieval — fall back to the
                # deterministic TF-IDF retriever instead.
                print(
                    f"[vector_store] live embeddings unavailable "
                    f"({type(exc).__name__}); falling back to TF-IDF retrieval"
                )
                self.mode = "mock"
        self.matrix = self._fit_tfidf(self.texts)

    # ----- live embeddings -----
    def _embed_live(self, texts: List[str]) -> np.ndarray:
        from langchain_openai import OpenAIEmbeddings

        emb = OpenAIEmbeddings(model="text-embedding-3-small")
        vecs = np.array(emb.embed_documents(texts), dtype=float)
        return _l2_normalize(vecs)

    def _embed_query_live(self, query: str) -> np.ndarray:
        from langchain_openai import OpenAIEmbeddings

        emb = OpenAIEmbeddings(model="text-embedding-3-small")
        return _l2_normalize(np.array([emb.embed_query(query)], dtype=float))[0]

    # ----- mock tf-idf -----
    def _fit_tfidf(self, texts: List[str]) -> np.ndarray:
        docs = [_tokens(t) for t in texts]
        vocab = {}
        for d in docs:
            for tok in set(d):
                vocab.setdefault(tok, len(vocab))
        self._vocab = vocab
        n = len(docs)
        df = np.zeros(len(vocab))
        for d in docs:
            for tok in set(d):
                df[vocab[tok]] += 1
        self._idf = np.log((1 + n) / (1 + df)) + 1.0
        rows = [self._tfidf_vector(d) for d in docs]
        return _l2_normalize(np.array(rows))

    def _tfidf_vector(self, toks: List[str]) -> np.ndarray:
        vec = np.zeros(len(self._vocab))
        if not toks:
            return vec
        counts = Counter(toks)
        for tok, c in counts.items():
            idx = self._vocab.get(tok)
            if idx is not None:
                vec[idx] = (c / len(toks)) * self._idf[idx]
        return vec

    def _embed_query_mock(self, query: str) -> np.ndarray:
        return _l2_normalize(np.array([self._tfidf_vector(_tokens(query))]))[0]

    # ----- retrieval -----
    def retrieve(
        self, query: str, k: int = 2, source_prefix: Optional[str] = None
    ) -> List[Tuple[str, str, float]]:
        """Return up to ``k`` (source, snippet, score) tuples, best first."""
        if self.matrix is None or not self.texts:
            return []
        try:
            qv = (
                self._embed_query_live(query)
                if self.mode == "live"
                else self._embed_query_mock(query)
            )
        except Exception:
            # A live query-embedding failure degrades to "no evidence" rather
            # than crashing the retrieval node.
            return []
        scores = self.matrix @ qv
        order = np.argsort(-scores)
        out: List[Tuple[str, str, float]] = []
        for idx in order:
            src = self.sources[idx]
            if source_prefix and not src.startswith(source_prefix):
                continue
            snippet = self.texts[idx].strip().replace("\n", " ")
            out.append((src, snippet[:400], round(float(scores[idx]), 4)))
            if len(out) >= k:
                break
        return out


def _l2_normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


# --------------------------------------------------------------------------- #
# Singleton accessor (build once, reuse across nodes).
# --------------------------------------------------------------------------- #
_STORE: Optional[VectorStore] = None


def get_store() -> VectorStore:
    global _STORE
    if _STORE is None:
        store = VectorStore()
        store.add_markdown("playbook.md")
        store.add_markdown("policy.md")
        store.build()
        _STORE = store
    return _STORE


def reset_store() -> None:
    """Drop the cached store (used by tests when toggling mock/live)."""
    global _STORE
    _STORE = None
