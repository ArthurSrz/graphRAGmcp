#!/usr/bin/env python3
"""Test script for embedding cache implementation."""

import asyncio
import sys
import os
import tempfile
import shutil
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from nano_graphrag._storage.vdb_nanovectordb import (
    NanoVectorDBStorage,
    get_embedding_cache_stats,
    embedding_cache,
    _get_text_hash
)
from nano_graphrag._utils import EmbeddingFunc, wrap_embedding_func_with_attrs


# Mock embedding function for testing
@wrap_embedding_func_with_attrs(embedding_dim=128, max_token_size=512)
async def mock_embedding_func(texts: list[str]) -> np.ndarray:
    """Simple mock embedding function that returns random vectors."""
    print(f"  [Mock Embedding] Computing embeddings for {len(texts)} texts")
    await asyncio.sleep(0.1)  # Simulate API delay
    return np.random.rand(len(texts), 128).astype(np.float32)


async def test_embedding_cache():
    """Test the embedding cache functionality."""

    print("\n=== Testing Embedding Cache Implementation ===\n")

    # Create temporary working directory
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary directory: {temp_dir}")

    try:
        # Clear any existing cache
        embedding_cache.clear()

        # Initialize storage
        config = {
            "working_dir": temp_dir,
            "embedding_batch_num": 10,
            "query_better_than_threshold": 0.2
        }

        storage = NanoVectorDBStorage(
            namespace="test",
            global_config=config,
            embedding_func=mock_embedding_func,
            meta_fields={"content"}
        )

        # Test 1: First upsert (all cache misses)
        print("\n--- Test 1: First upsert (expect all misses) ---")
        test_data = {
            "doc1": {"content": "This is the first document"},
            "doc2": {"content": "This is the second document"},
            "doc3": {"content": "This is the third document"},
        }

        await storage.upsert(test_data)
        stats = get_embedding_cache_stats()
        print(f"Cache stats after first upsert: {stats}")
        assert stats["valid_entries"] == 3, "Should have 3 cached embeddings"

        # Test 2: Second upsert with same data (all cache hits)
        print("\n--- Test 2: Second upsert with same data (expect all hits) ---")
        await storage.upsert(test_data)
        stats = get_embedding_cache_stats()
        print(f"Cache stats after second upsert: {stats}")
        assert stats["valid_entries"] == 3, "Should still have 3 cached embeddings"

        # Test 3: Mixed upsert (some hits, some misses)
        print("\n--- Test 3: Mixed upsert (expect 2 hits, 2 misses) ---")
        mixed_data = {
            "doc1": {"content": "This is the first document"},  # hit
            "doc3": {"content": "This is the third document"},  # hit
            "doc4": {"content": "This is a new document"},      # miss
            "doc5": {"content": "Another new document"},        # miss
        }

        await storage.upsert(mixed_data)
        stats = get_embedding_cache_stats()
        print(f"Cache stats after mixed upsert: {stats}")
        assert stats["valid_entries"] == 5, "Should have 5 cached embeddings"

        # Test 4: Query caching
        print("\n--- Test 4: Query caching (first query = miss, second = hit) ---")
        query_text = "What is this about?"

        print("First query (expect cache miss)...")
        results1 = await storage.query(query_text, top_k=2)
        stats = get_embedding_cache_stats()
        print(f"Cache stats after first query: {stats}")
        assert stats["valid_entries"] == 6, "Should have 6 cached embeddings (5 docs + 1 query)"

        print("Second query with same text (expect cache hit)...")
        results2 = await storage.query(query_text, top_k=2)
        stats = get_embedding_cache_stats()
        print(f"Cache stats after second query: {stats}")
        assert stats["valid_entries"] == 6, "Should still have 6 cached embeddings"

        # Test 5: Verify hash-based caching
        print("\n--- Test 5: Verify hash-based caching ---")
        text1 = "This is a test"
        text2 = "This is a test"  # Same content
        hash1 = _get_text_hash(text1)
        hash2 = _get_text_hash(text2)
        print(f"Hash 1: {hash1[:16]}...")
        print(f"Hash 2: {hash2[:16]}...")
        assert hash1 == hash2, "Same text should produce same hash"

        print("\n=== All tests passed! ===\n")

        # Print final cache stats
        final_stats = get_embedding_cache_stats()
        print("Final cache statistics:")
        for key, value in final_stats.items():
            print(f"  {key}: {value}")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up temporary directory: {temp_dir}")


if __name__ == "__main__":
    asyncio.run(test_embedding_cache())
