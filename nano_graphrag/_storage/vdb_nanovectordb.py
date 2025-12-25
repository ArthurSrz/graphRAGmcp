import asyncio
import os
import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np
from nano_vectordb import NanoVectorDB

from .._utils import logger
from ..base import BaseVectorStorage


# ============================================================================
# Embedding Cache (Feature 006-graph-optimization, T027)
# ============================================================================

class EmbeddingCache:
    """
    Global cache for embedding vectors to avoid redundant API calls.

    Problem: Identical text strings are re-embedded on every query,
    wasting API calls and adding 7.5-15s per repeated embedding batch.

    Solution: Hash-based cache with 24-hour TTL.
    """

    def __init__(self, ttl_seconds: int = 86400, max_entries: int = 10000):
        self._cache: Dict[str, Tuple[np.ndarray, float]] = {}  # hash -> (embedding, timestamp)
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0

    def _hash_text(self, text: str) -> str:
        """Generate hash key for text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def get(self, text: str) -> np.ndarray | None:
        """Get cached embedding if valid."""
        key = self._hash_text(text)
        if key not in self._cache:
            self._misses += 1
            return None

        embedding, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl_seconds:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        return embedding

    def put(self, text: str, embedding: np.ndarray):
        """Cache an embedding."""
        # Evict oldest if at capacity
        if len(self._cache) >= self._max_entries:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        key = self._hash_text(text)
        self._cache[key] = (embedding, time.time())

    def get_batch(self, texts: List[str]) -> Tuple[List[np.ndarray | None], List[int]]:
        """
        Get cached embeddings for a batch.
        Returns (embeddings, uncached_indices) where uncached_indices
        contains indices of texts that need to be computed.
        """
        results = []
        uncached_indices = []
        for i, text in enumerate(texts):
            cached = self.get(text)
            results.append(cached)
            if cached is None:
                uncached_indices.append(i)
        return results, uncached_indices

    def put_batch(self, texts: List[str], embeddings: np.ndarray, indices: List[int]):
        """Cache embeddings for specific indices."""
        for i, idx in enumerate(indices):
            self.put(texts[idx], embeddings[i])

    def stats(self) -> dict:
        return {
            "size": len(self._cache),
            "max_entries": self._max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0
        }


# Global embedding cache
_embedding_cache = EmbeddingCache(ttl_seconds=86400, max_entries=10000)


@dataclass
class NanoVectorDBStorage(BaseVectorStorage):
    cosine_better_than_threshold: float = 0.2

    def __post_init__(self):

        self._client_file_name = os.path.join(
            self.global_config["working_dir"], f"vdb_{self.namespace}.json"
        )
        self._max_batch_size = self.global_config["embedding_batch_num"]
        self._client = NanoVectorDB(
            self.embedding_func.embedding_dim, storage_file=self._client_file_name
        )
        self.cosine_better_than_threshold = self.global_config.get(
            "query_better_than_threshold", self.cosine_better_than_threshold
        )

    async def upsert(self, data: dict[str, dict]):
        logger.info(f"Inserting {len(data)} vectors to {self.namespace}")
        if not len(data):
            logger.warning("You insert an empty data to vector DB")
            return []
        list_data = [
            {
                "__id__": k,
                **{k1: v1 for k1, v1 in v.items() if k1 in self.meta_fields},
            }
            for k, v in data.items()
        ]
        contents = [v["content"] for v in data.values()]
        batches = [
            contents[i : i + self._max_batch_size]
            for i in range(0, len(contents), self._max_batch_size)
        ]
        embeddings_list = await asyncio.gather(
            *[self.embedding_func(batch) for batch in batches]
        )
        embeddings = np.concatenate(embeddings_list)
        for i, d in enumerate(list_data):
            d["__vector__"] = embeddings[i]
        results = self._client.upsert(datas=list_data)
        return results

    async def query(self, query: str, top_k=5):
        # Feature 006-graph-optimization T027: Check embedding cache first
        cached_embedding = _embedding_cache.get(query)

        if cached_embedding is not None:
            embedding = cached_embedding
            logger.debug(f"Embedding cache hit for query: {query[:50]}...")
        else:
            embedding = await self.embedding_func([query])
            embedding = embedding[0]
            _embedding_cache.put(query, embedding)
            logger.debug(f"Embedding cache miss for query: {query[:50]}...")

        results = self._client.query(
            query=embedding,
            top_k=top_k,
            better_than_threshold=self.cosine_better_than_threshold,
        )
        results = [
            {**dp, "id": dp["__id__"], "distance": dp["__metrics__"]} for dp in results
        ]
        return results

    async def index_done_callback(self):
        self._client.save()
