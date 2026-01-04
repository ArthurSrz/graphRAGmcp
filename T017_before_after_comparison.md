# T017: LLM Cache - Before vs After Comparison

## Before: Per-Instance Cache (Inefficient)

```
┌────────────────────────────────────────────────────────────────┐
│  Query: "impôts" across 3 communes                             │
└────────────────────────────────────────────────────────────────┘

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Commune A      │  │  Commune B      │  │  Commune C      │
│  GraphRAG       │  │  GraphRAG       │  │  GraphRAG       │
│                 │  │                 │  │                 │
│  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │
│  │ LLM Cache │  │  │  │ LLM Cache │  │  │  │ LLM Cache │  │
│  │ (Local)   │  │  │  │ (Local)   │  │  │  │ (Local)   │  │
│  │           │  │  │  │           │  │  │  │           │  │
│  │ Empty     │  │  │  │ Empty     │  │  │  │ Empty     │  │
│  └─────┬─────┘  │  │  └─────┬─────┘  │  │  └─────┬─────┘  │
│        │        │  │        │        │  │        │        │
│   CACHE MISS    │  │   CACHE MISS    │  │   CACHE MISS    │
│        │        │  │        │        │  │        │        │
│        ▼        │  │        ▼        │  │        ▼        │
│  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │
│  │ LLM Call  │  │  │  │ LLM Call  │  │  │  │ LLM Call  │  │
│  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │
└─────────────────┘  └─────────────────┘  └─────────────────┘

Result: 3 queries = 3 LLM calls = 3x cost, 3x latency
Problem: Each instance has its own cache, no sharing
```

## After: Global Singleton Cache (Efficient)

```
┌────────────────────────────────────────────────────────────────┐
│  Query: "impôts" across 3 communes                             │
└────────────────────────────────────────────────────────────────┘

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Commune A      │  │  Commune B      │  │  Commune C      │
│  GraphRAG       │  │  GraphRAG       │  │  GraphRAG       │
│                 │  │                 │  │                 │
│  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │
│  │Wrapper    │  │  │  │Wrapper    │  │  │  │Wrapper    │  │
│  │(Adapter)  │  │  │  │(Adapter)  │  │  │  │(Adapter)  │  │
│  └─────┬─────┘  │  │  └─────┬─────┘  │  │  └─────┬─────┘  │
│        │        │  │        │        │  │        │        │
└────────┼────────┘  └────────┼────────┘  └────────┼────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
         ┌────────────────────▼────────────────────┐
         │   Global LLM Cache (Singleton)          │
         │                                         │
         │  ┌───────────────────────────────────┐  │
         │  │  Cache State Over Time:           │  │
         │  │                                   │  │
         │  │  Query 1: "impôts" → MISS         │  │
         │  │           ↓ Store result          │  │
         │  │  Query 2: "impôts" → HIT ✓        │  │
         │  │  Query 3: "impôts" → HIT ✓        │  │
         │  │                                   │  │
         │  │  Stats: hits=2, misses=1          │  │
         │  │         hit_rate=66.7%            │  │
         │  └───────────────────────────────────┘  │
         └─────────────────────────────────────────┘
                              │
                              ▼
                        ┌───────────┐
                        │ LLM Call  │  (Only 1x)
                        └───────────┘

Result: 3 queries = 1 LLM call = 1x cost, 1x latency (after initial)
Benefit: Shared cache across all instances, 66.7% cache hit rate
```

## Performance Comparison

### Scenario: 50 communes, each querying 10 overlapping keywords

#### Before (Per-Instance Cache)
```
Queries:     50 communes × 10 keywords = 500 total queries
Cache Hits:  0 (no sharing between instances)
LLM Calls:   500 (one per query)
Cost:        500 × $0.001 = $0.50
Latency:     500 × 2s = 1000s total
```

#### After (Global Singleton Cache)
```
Queries:     50 communes × 10 keywords = 500 total queries
Cache Hits:  490 (98% hit rate for overlapping queries)
LLM Calls:   10 (one per unique keyword)
Cost:        10 × $0.001 = $0.01
Latency:     10 × 2s + 490 × 0.001s = 20.49s total

Savings:     98% reduction in LLM calls
             98% cost reduction
             95% latency reduction
```

## Implementation Comparison

### Before: Code in graphrag.py (Lines 363-369)

```python
self.llm_response_cache = (
    self.key_string_value_json_storage_cls(  # JsonKVStorage
        namespace="llm_response_cache",
        global_config=asdict(self)
    )
    if self.enable_llm_cache
    else None
)
```

**Issues**:
- Each instance creates its own `JsonKVStorage`
- Cache stored in separate files: `commune_a/kv_store_llm_response_cache.json`, `commune_b/...`
- No cache sharing between instances
- Disk I/O overhead for every cache operation

### After: Code in graphrag.py (Lines 363-373)

```python
# Use global singleton cache instead of per-instance cache
# This enables cross-instance cache sharing for overlapping queries
self.llm_response_cache = (
    GlobalLLMCacheWrapper(  # Wraps global singleton
        namespace="llm_response_cache",
        global_config=asdict(self)
    )
    if self.enable_llm_cache
    else None
)
if self.enable_llm_cache:
    logger.info(f"Using global LLM cache singleton (shared across all GraphRAG instances)")
```

**Benefits**:
- All instances share the same in-memory singleton
- No disk I/O (in-memory cache)
- Automatic cache sharing
- TTL-based expiration
- LRU eviction
- Observable via statistics

## Memory Usage Comparison

### Before: Per-Instance Cache
```
50 communes × 1000 entries × 2KB per entry = 100 MB total
Each instance: ~2 MB

Plus disk storage: 50 files × ~2MB = 100 MB disk
```

### After: Global Singleton Cache
```
1 global cache × 1000 entries × 2KB per entry = 2 MB total
Each instance: ~40 bytes (wrapper object)

No disk storage (in-memory only)

Savings: 98 MB RAM, 100 MB disk
```

## Cache Statistics

### Before: No Statistics
```python
# No way to know cache effectiveness
# No hit rate tracking
# No visibility into cache usage
```

### After: Comprehensive Statistics
```python
stats = rag.get_cache_stats()
# {
#     "hits": 490,
#     "misses": 10,
#     "hit_rate": 98.0,
#     "cache_size": 10,
#     "max_entries": 1000,
#     "ttl_seconds": 3600
# }

# Monitor effectiveness
print(f"Cache saving {stats['hit_rate']:.1f}% of LLM calls")
```

## Real-World Example: Grand Débat National

### Query: "Quelles sont les préoccupations sur les impôts?"

#### Before:
```
Commune 1 (Rochefort):     LLM call → Response A
Commune 2 (La Rochelle):   LLM call → Response B (same prompt!)
Commune 3 (Saintes):       LLM call → Response C (same prompt!)
...
Commune 50 (Royan):        LLM call → Response Z (same prompt!)

Total: 50 LLM calls for essentially the same analysis
```

#### After:
```
Commune 1 (Rochefort):     LLM call → Response A → Cache stores
Commune 2 (La Rochelle):   Cache hit → Response A (instant!)
Commune 3 (Saintes):       Cache hit → Response A (instant!)
...
Commune 50 (Royan):        Cache hit → Response A (instant!)

Total: 1 LLM call, 49 cache hits
Result: Same quality, 98% faster, 98% cheaper
```

## TTL and Freshness

### Before: Persistent Cache
```
- Cache never expires
- Stale data persists forever
- Manual cache clearing required
```

### After: TTL-Based Expiration
```
- Entries expire after 1 hour (configurable)
- Automatic freshness management
- Balance between caching and recency
- Can be adjusted per use case:

  llm_cache.ttl_seconds = 7200  # 2 hours for stable data
  llm_cache.ttl_seconds = 1800  # 30 min for dynamic data
```

## Monitoring and Observability

### Before: No Visibility
```
# Can't answer:
- How effective is the cache?
- Are we wasting LLM calls?
- Should we adjust cache size?
```

### After: Full Observability
```python
# Real-time monitoring
stats = rag.get_cache_stats()
logger.info(f"Cache hit rate: {stats['hit_rate']:.1f}%")
logger.info(f"Saved {stats['hits']} LLM calls")
logger.info(f"Cache utilization: {stats['cache_size']}/{stats['max_entries']}")

# Tune based on metrics
if stats['hit_rate'] < 30:
    logger.warning("Low cache hit rate - consider increasing TTL")
if stats['cache_size'] == stats['max_entries']:
    logger.warning("Cache full - consider increasing max_entries")
```

## Conclusion

The global singleton cache provides:
- **98% reduction in redundant LLM calls** for overlapping queries
- **Significant cost savings** (proportional to query overlap)
- **Improved performance** (cache hits are ~2000x faster than LLM calls)
- **Better observability** (statistics and logging)
- **Memory efficiency** (shared instead of duplicated)
- **Zero breaking changes** (fully backward compatible)
