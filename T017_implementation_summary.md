# T017: Shared LLM Response Cache Singleton - Implementation Summary

**Date**: 2025-12-25
**Task**: Graph Performance Optimization (006-graph-optimization) - Phase 4, User Story 2
**File Modified**: `/Users/arthursarazin/Documents/graphRAGmcp/nano_graphrag/graphrag.py`

## Problem Statement

Previously, each GraphRAG instance (one per commune) maintained its own LLM response cache. When multiple communes queried with overlapping keywords (e.g., "impôts", "santé"), the system would make redundant LLM calls instead of reusing cached responses.

## Solution: Global Singleton Cache

Implemented a thread-safe singleton cache that is shared across all GraphRAG instances, enabling cross-instance cache hits for overlapping queries.

## Implementation Details

### 1. LLMResponseCache Singleton Class

**Location**: Lines 53-148 in `graphrag.py`

**Features**:
- Singleton pattern using `__new__` method
- SHA256 hashing of (model, prompt) for cache keys
- TTL-based expiration (default: 1 hour, 3600 seconds)
- LRU eviction when max_entries (1000) is reached
- Hit/miss statistics tracking with percentage calculation

**Key Methods**:
- `get(prompt, model)` - Retrieve cached response with TTL check
- `set(prompt, model, response)` - Store response with LRU eviction
- `clear()` - Clear all entries and reset statistics
- `get_stats()` - Return cache metrics (hits, misses, hit_rate, size, etc.)

**Statistics Tracked**:
```python
{
    "hits": int,           # Number of cache hits
    "misses": int,         # Number of cache misses
    "hit_rate": float,     # Percentage (hits/total * 100)
    "cache_size": int,     # Current number of entries
    "max_entries": int,    # Maximum capacity (1000)
    "ttl_seconds": int     # Time-to-live (3600)
}
```

### 2. GlobalLLMCacheWrapper Adapter Class

**Location**: Lines 151-231 in `graphrag.py`

**Purpose**: Adapts the singleton cache to the `BaseKVStorage` interface expected by LLM functions in `_llm.py`.

**Key Methods**:
- `get_by_id(id)` - Compatible with existing cache lookup in `_llm.py`
- `upsert(data)` - Compatible with existing cache storage in `_llm.py`
- `all_keys()`, `get_by_ids()`, `filter_keys()`, `drop()` - Standard BaseKVStorage interface
- `index_done_callback()` - No-op for in-memory cache

**Integration Point**: Lines 363-373
```python
self.llm_response_cache = (
    GlobalLLMCacheWrapper(
        namespace="llm_response_cache", global_config=asdict(self)
    )
    if self.enable_llm_cache
    else None
)
```

### 3. Public API Methods

**Location**: Lines 570-587 in `graphrag.py`

Added two public methods to GraphRAG class:

```python
def get_cache_stats(self) -> Dict[str, Union[int, float]]:
    """Get statistics about the global LLM cache."""
    return llm_cache.get_stats()

def clear_cache(self):
    """Clear all entries from the global LLM cache."""
    llm_cache.clear()
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Multiple GraphRAG Instances              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Commune A    │  │ Commune B    │  │ Commune C    │      │
│  │ GraphRAG     │  │ GraphRAG     │  │ GraphRAG     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
│  ┌─────────────────────────▼──────────────────────────┐     │
│  │       GlobalLLMCacheWrapper (Adapter)              │     │
│  │       implements BaseKVStorage interface           │     │
│  └─────────────────────────┬──────────────────────────┘     │
│                            │                                 │
│  ┌─────────────────────────▼──────────────────────────┐     │
│  │       LLMResponseCache (Singleton)                 │     │
│  │  ┌──────────────────────────────────────────────┐  │     │
│  │  │ Cache: {hash: (response, timestamp)}         │  │     │
│  │  │ - TTL: 3600s                                 │  │     │
│  │  │ - Max: 1000 entries                          │  │     │
│  │  │ - LRU eviction                               │  │     │
│  │  │ - Stats: hits=X, misses=Y, hit_rate=Z%       │  │     │
│  │  └──────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

1. **Cache Lookup Flow**:
   ```
   LLM function in _llm.py
   → calls hashing_kv.get_by_id(args_hash)
   → GlobalLLMCacheWrapper.get_by_id()
   → LLMResponseCache.get() [via direct dict lookup]
   → Returns cached response or None
   ```

2. **Cache Storage Flow**:
   ```
   LLM function in _llm.py
   → calls hashing_kv.upsert({hash: {"return": response, "model": model}})
   → GlobalLLMCacheWrapper.upsert()
   → LLMResponseCache.set() [stores in singleton cache]
   → LRU eviction if cache is full
   ```

3. **Cross-Instance Benefits**:
   - Commune A queries "impôts" → Cache miss, LLM call, cache stores
   - Commune B queries "impôts" → **Cache hit**, no LLM call
   - Commune C queries "impôts" → **Cache hit**, no LLM call

   Result: 3 queries, 1 LLM call instead of 3

## Compatibility

**No Changes Required to `_llm.py`**: The existing LLM functions continue to use the `hashing_kv` parameter exactly as before. The `GlobalLLMCacheWrapper` adapter ensures full compatibility with the `BaseKVStorage` interface.

**Existing Functions That Use Cache**:
- `openai_complete_if_cache()` - Line 49-74 in `_llm.py`
- `amazon_bedrock_complete_if_cache()` - Line 82-121 in `_llm.py`
- `azure_openai_complete_if_cache()` - Line 230-255 in `_llm.py`

## Testing

**Test File**: `/Users/arthursarazin/Documents/graphRAGmcp/test_llm_cache_singleton.py`

**Test Coverage**:
1. ✓ Singleton pattern verification
2. ✓ Basic cache operations (get/set)
3. ✓ Statistics tracking (hits, misses, hit rate)
4. ✓ Cross-instance cache sharing
5. ✓ LRU eviction behavior

**Test Results**: All tests passed

## Performance Metrics

The cache tracks comprehensive statistics accessible via `get_cache_stats()`:

```python
{
    "hits": 2,              # Successful cache retrievals
    "misses": 1,            # Cache misses requiring LLM calls
    "hit_rate": 66.67,      # Percentage of requests served from cache
    "cache_size": 1,        # Current entries in cache
    "max_entries": 1000,    # Maximum capacity
    "ttl_seconds": 3600     # Entry lifetime (1 hour)
}
```

## Usage Example

```python
from nano_graphrag.graphrag import GraphRAG

# Create multiple GraphRAG instances
rag1 = GraphRAG(working_dir="./commune_a")
rag2 = GraphRAG(working_dir="./commune_b")

# Both instances automatically share the same cache
# No additional configuration required

# Check cache statistics
stats = rag1.get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate']:.1f}%")

# Clear cache if needed (affects all instances)
rag1.clear_cache()
```

## Logging

The implementation includes comprehensive logging:

- `INFO`: "Using global LLM cache singleton (shared across all GraphRAG instances)"
- `DEBUG`: "LLM cache hit for {model} (hits: X, misses: Y, hit_rate: Z%)"
- `DEBUG`: "LLM response cached for {model} (cache size: N)"
- `DEBUG`: "LLM cache evicted oldest entry (cache size: N)"
- `INFO`: "LLM cache cleared"

## Configuration

The cache has sensible defaults that can be modified if needed:

```python
from nano_graphrag.graphrag import llm_cache

# Adjust TTL (in seconds)
llm_cache.ttl_seconds = 7200  # 2 hours

# Adjust max capacity
llm_cache.max_entries = 2000  # 2000 entries

# Clear and reset
llm_cache.clear()
```

## Benefits

1. **Reduced LLM Costs**: Overlapping queries across communes share cached responses
2. **Improved Performance**: Cache hits avoid network latency and LLM processing time
3. **Zero Breaking Changes**: Fully compatible with existing codebase
4. **Observable**: Statistics provide visibility into cache effectiveness
5. **Memory Efficient**: LRU eviction prevents unbounded growth
6. **Time-Aware**: TTL prevents serving stale responses

## Files Modified

- **Modified**: `/Users/arthursarazin/Documents/graphRAGmcp/nano_graphrag/graphrag.py`
  - Added `LLMResponseCache` singleton class (lines 53-148)
  - Added `GlobalLLMCacheWrapper` adapter class (lines 151-231)
  - Updated `__post_init__` to use global cache (lines 363-373)
  - Added `get_cache_stats()` and `clear_cache()` methods (lines 570-587)
  - Added `hashlib` import (line 2)

- **Created**: `/Users/arthursarazin/Documents/graphRAGmcp/test_llm_cache_singleton.py`
  - Comprehensive test suite with 5 test cases

## Next Steps

1. Monitor cache hit rates in production to tune `ttl_seconds` and `max_entries`
2. Consider adding cache persistence for longer-term storage
3. Add cache warming for common queries
4. Implement cache preloading based on historical query patterns

## Completion Status

✅ **Task T017 Complete**

- Global singleton cache implemented
- Wrapper adapter created for BaseKVStorage compatibility
- All tests passing
- No breaking changes to existing code
- Logging and statistics integrated
- Documentation complete
