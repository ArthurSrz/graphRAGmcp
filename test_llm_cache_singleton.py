#!/usr/bin/env python3
"""
Test script to verify the global LLM cache singleton implementation.

This script demonstrates that:
1. Multiple GraphRAG instances share the same cache
2. Cache hits work across instances
3. Statistics are shared globally
"""

import asyncio
import sys
import os

# Add the parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from nano_graphrag.graphrag import LLMResponseCache, llm_cache, GraphRAG


def test_singleton_pattern():
    """Test that LLMResponseCache is truly a singleton."""
    print("Testing singleton pattern...")

    cache1 = LLMResponseCache()
    cache2 = LLMResponseCache()

    assert cache1 is cache2, "Cache instances should be identical"
    assert cache1 is llm_cache, "Should use global instance"

    print("✓ Singleton pattern verified")


def test_cache_operations():
    """Test basic cache operations."""
    print("\nTesting cache operations...")

    # Clear cache to start fresh
    llm_cache.clear()

    # Test set and get
    llm_cache.set("test prompt", "gpt-4", "test response")
    result = llm_cache.get("test prompt", "gpt-4")

    assert result == "test response", f"Expected 'test response', got '{result}'"

    # Test cache miss
    result = llm_cache.get("nonexistent prompt", "gpt-4")
    assert result is None, "Should return None for cache miss"

    print("✓ Cache operations work correctly")


def test_statistics():
    """Test cache statistics tracking."""
    print("\nTesting statistics...")

    llm_cache.clear()

    # Generate some hits and misses
    llm_cache.set("prompt1", "gpt-4", "response1")
    llm_cache.get("prompt1", "gpt-4")  # hit
    llm_cache.get("prompt1", "gpt-4")  # hit
    llm_cache.get("nonexistent", "gpt-4")  # miss

    stats = llm_cache.get_stats()

    print(f"  Stats: {stats}")
    assert stats["hits"] == 2, f"Expected 2 hits, got {stats['hits']}"
    assert stats["misses"] == 1, f"Expected 1 miss, got {stats['misses']}"
    assert abs(stats["hit_rate"] - 66.67) < 0.1, f"Expected ~66.67% hit rate, got {stats['hit_rate']}"

    print("✓ Statistics tracking works correctly")


async def test_cross_instance_sharing():
    """Test that cache is shared across GraphRAG instances."""
    print("\nTesting cross-instance cache sharing...")

    llm_cache.clear()

    # Create two GraphRAG instances
    rag1 = GraphRAG(
        working_dir="/tmp/test_rag1",
        enable_llm_cache=True,
        always_create_working_dir=False
    )

    rag2 = GraphRAG(
        working_dir="/tmp/test_rag2",
        enable_llm_cache=True,
        always_create_working_dir=False
    )

    # Both should reference the global cache
    assert rag1.llm_response_cache._global_cache is llm_cache
    assert rag2.llm_response_cache._global_cache is llm_cache
    assert rag1.llm_response_cache._global_cache is rag2.llm_response_cache._global_cache

    print("  ✓ Both instances share the same global cache")

    # Test that cache operations in one instance affect the other
    initial_stats = llm_cache.get_stats()
    print(f"  Initial stats: {initial_stats}")

    # Simulate a cache entry (using the wrapper interface)
    await rag1.llm_response_cache.upsert({
        "test_hash_123": {"return": "cached response", "model": "gpt-4"}
    })

    # Retrieve from the other instance
    result = await rag2.llm_response_cache.get_by_id("test_hash_123")

    assert result is not None, "Cache entry should be accessible from second instance"
    assert result["return"] == "cached response", f"Expected 'cached response', got '{result['return']}'"

    print("  ✓ Cache entries are shared between instances")

    # Check statistics
    stats1 = rag1.get_cache_stats()
    stats2 = rag2.get_cache_stats()

    assert stats1 == stats2, "Statistics should be identical across instances"
    print(f"  ✓ Shared statistics: {stats1}")


def test_lru_eviction():
    """Test LRU eviction when cache is full."""
    print("\nTesting LRU eviction...")

    llm_cache.clear()
    original_max = llm_cache.max_entries

    # Set a small max_entries for testing
    llm_cache.max_entries = 3

    try:
        # Fill cache
        llm_cache.set("prompt1", "gpt-4", "response1")
        llm_cache.set("prompt2", "gpt-4", "response2")
        llm_cache.set("prompt3", "gpt-4", "response3")

        assert len(llm_cache.cache) == 3, f"Expected 3 entries, got {len(llm_cache.cache)}"

        # Add one more - should evict oldest
        llm_cache.set("prompt4", "gpt-4", "response4")

        assert len(llm_cache.cache) == 3, f"Expected 3 entries after eviction, got {len(llm_cache.cache)}"

        # First entry should be evicted
        result = llm_cache.get("prompt1", "gpt-4")
        assert result is None, "Oldest entry should have been evicted"

        # Newest entry should still be there
        result = llm_cache.get("prompt4", "gpt-4")
        assert result == "response4", "Newest entry should be in cache"

        print("✓ LRU eviction works correctly")

    finally:
        # Restore original max_entries
        llm_cache.max_entries = original_max
        llm_cache.clear()


def main():
    """Run all tests."""
    print("=" * 60)
    print("LLM Cache Singleton Implementation Tests")
    print("=" * 60)

    try:
        test_singleton_pattern()
        test_cache_operations()
        test_statistics()
        asyncio.run(test_cross_instance_sharing())
        test_lru_eviction()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
