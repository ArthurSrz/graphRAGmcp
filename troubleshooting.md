# Troubleshooting

## Railway Deployment Issues

### FastMCP.run() TypeError: unexpected keyword argument 'host'

**Problem:**
```
TypeError: FastMCP.run() got an unexpected keyword argument 'host'
```

**Cause:**
The MCP SDK 1.0+ changed the `FastMCP.run()` API. The `host` and `port` parameters are no longer accepted directly in the `run()` method for HTTP transport.

**Solution:**
Use `uvicorn` to run the ASGI app directly instead of relying on `mcp.run()`:

```python
# Before (broken in mcp>=1.0.0)
mcp.run(transport="streamable-http", host=args.host, port=args.port)

# After (works with mcp>=1.0.0)
import uvicorn
uvicorn.run(
    mcp.streamable_http_app(),
    host=args.host,
    port=args.port,
    log_level="info"
)
```

**Requirements:**
Add `uvicorn>=0.30.0` to `requirements.txt`.

**Date fixed:** 2025-12-22

---

### HTTP 421 "Invalid Host header" on Railway

**Problem:**
```
HTTP/2 421
Invalid Host header
```

**Cause:**
Railway uses a reverse proxy (railway-edge) to route requests. Uvicorn needs to be configured to trust proxy headers, otherwise it rejects requests with mismatched Host headers.

**Solution:**
Add proxy configuration to uvicorn:

```python
uvicorn.run(
    mcp.streamable_http_app(),
    host=args.host,
    port=args.port,
    log_level="info",
    proxy_headers=True,        # Trust X-Forwarded-* headers
    forwarded_allow_ips="*"    # Accept forwarded headers from any IP
)
```

**Date fixed:** 2025-12-22

---

### MCP SDK DNS Rebinding Protection (Invalid Host header)

**Problem:**
```
Invalid Host header (HTTP 421)
```

**Cause:**
MCP Python SDK 1.x introduced DNS rebinding protection. When deployed behind a reverse proxy (Railway, Cloud Run, etc.), the Host header doesn't match the allowed list.

**Solution:**
Disable DNS rebinding protection when Railway handles security at the edge:

```python
from mcp.server.transport_security import TransportSecuritySettings

transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

mcp = FastMCP("my_server", transport_security=transport_security)
```

**Reference:** https://github.com/modelcontextprotocol/python-sdk/issues/1798

**Date fixed:** 2025-12-22

---

### Pydantic Validation Error: "Field required" for params

**Problem:**
```
Error executing tool grand_debat_query: 1 validation error for grand_debat_queryArguments
params
  Field required [type=missing, input_value={'mode': 'global', 'query': '...', 'commune_id': 'Rochefort'}, input_type=dict]
```

**Cause:**
Tools defined with nested Pydantic models like `async def my_tool(params: MyModel)` expect clients to wrap arguments in a `params` object:
```json
{"params": {"commune_id": "X", "query": "Y"}}
```

But most MCP clients (including Dust.tt) send flat arguments:
```json
{"commune_id": "X", "query": "Y"}
```

**Solution:**
Use flat function parameters with `Annotated` types instead of nested Pydantic models:

```python
from typing import Annotated
from pydantic import Field

# Before (requires nested params - breaks Dust.tt)
class QueryInput(BaseModel):
    commune_id: str
    query: str

@mcp.tool()
async def my_tool(params: QueryInput) -> str:
    commune_id = params.commune_id
    ...

# After (accepts flat arguments - works with Dust.tt)
@mcp.tool()
async def my_tool(
    commune_id: Annotated[str, Field(description="Commune ID")],
    query: Annotated[str, Field(description="Query text")]
) -> str:
    # Use commune_id and query directly
    ...
```

**Date fixed:** 2025-12-22

---

### KeyError for Community ID (e.g., 'L0C3')

**Problem:**
```
ERROR:grand-debat-mcp:Query error for Saint_Jean_Dangely: 'L0C3'
```

**Cause:**
Some communes have 0 community reports (e.g., Saint_Jean_Dangely shows `Load KV community_reports with 0 data`). When the GraphRAG query tries to access community data by cluster ID, it fails because the community report doesn't exist.

The bug was in `nano_graphrag/_op.py` line 727: the code sorted all keys from `related_community_keys_counts` but some of those keys don't exist in `related_community_datas` (they were filtered out as None).

**Solution:**
Filter the sorted keys to only include those that exist in `related_community_datas`:

```python
# Before (crashes when community doesn't exist)
related_community_keys = sorted(
    related_community_keys_counts.keys(),
    ...
)

# After (safely handles missing communities)
related_community_keys = sorted(
    [k for k in related_community_keys_counts.keys() if k in related_community_datas],
    ...
)
```

**Date fixed:** 2025-12-22

---

### OpenAI 429 Rate Limit Errors on Cross-Commune Queries

**Problem:**
```
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 429 Too Many Requests"
```

**Cause:**
The `grand_debat_query_all` tool queries up to 50 communes in parallel. Each commune query triggers multiple OpenAI API calls (embeddings + chat completions). Without rate limiting, this overwhelms the OpenAI API rate limits.

**Solution:**
Use `asyncio.Semaphore` to limit concurrent API calls:

```python
import asyncio

MAX_CONCURRENT = 5  # Max 5 concurrent OpenAI API calls
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

async def query_single_commune(commune_info):
    """Query a single commune with rate limiting."""
    async with semaphore:  # Acquire semaphore before making API call
        # ... query logic here
        result = await rag.aquery(query, param=QueryParam(...))
        return result
```

The semaphore ensures only 5 communes are queried simultaneously, preventing API rate limit errors while still completing all 50 queries efficiently.

**Date fixed:** 2025-12-23

---

### Low Meaning Match Score in Opik (9-Commune Limitation)

**Problem:**
```
meaning_match score: 0.037 (3.7% average)
GraphRAG responses say "dans les 9 communes analysées" even though 55 communes are available
```

**Symptoms:**
- Opik evaluation shows very low semantic similarity between GraphRAG output and expected answers
- GraphRAG returns "no data found" for queries that should have results
- Responses mention analyzing only 9 communes instead of all 55
- hallucination score is high (57%) - system claims "no data" when data exists

**Root Cause:**
The `grand_debat_query_fast` function used keyword matching to select communities, then constrained the graph expansion to only those communes that had matching communities. This caused:
1. `select_communities_by_keywords()` returned communities from ~9 communes
2. `expand_via_index()` was called with `commune_filter=commune_ids` limiting traversal
3. Data in the other 46 communes was never searched

**Solution:**
Implemented **DUAL-STRATEGY** retrieval with corpus-wide coverage:

1. **Added `search_entities_globally()`** - searches entity names/descriptions across ALL 55 communes
2. **Combined seed sources** - use both community-based seeds AND global entity seeds
3. **Removed commune filtering** - pass `None` to `expand_via_index()` for cross-commune traversal
4. **Increased max_hops to 3** - deeper traversal to reach chunks

```python
# Phase 1a: Community selection (existing - for thematic context)
communities = await select_communities_by_keywords(query, max_communes)

# Phase 1b: Global entity search (NEW - corpus-wide)
global_entities = await search_entities_globally(query, max_results=100)

# Phase 2: Merge seeds from both strategies
all_seeds = list(set(community_seeds + global_seeds))

# Phase 3: Expansion WITHOUT commune filter (FIXED)
entities, paths = await expand_via_index(all_seeds, None, max_hops=3, max_results=500)
```

**Results:**
- Before: 9 communes searched, 16% coverage
- After: 51 communes with data, 92.7% coverage

**Performance Impact:**
- Global entity search: <100ms (GraphIndex is pre-loaded)
- Deeper traversal (3 hops): <100ms (O(1) neighbor lookups)
- Total query time remains <10s (LLM call dominates)

**Files changed:**
- `server.py`: Added `search_entities_globally()`, modified `grand_debat_query_fast()`

**Date fixed:** 2026-01-03

---

### Fast Graph Traversal to Chunks (Slow Source Quote Retrieval)

**Problem:**
```
Chunk retrieval: 500ms+ per query (file I/O)
Source quotes require loading JSON files from disk during query execution
```

**Symptoms:**
- Queries with `include_sources=True` are slower than expected
- Each query opens 20-50 JSON files to load chunk content
- File I/O blocks during query execution

**Root Cause:**
Chunks were NOT part of the GraphIndex. To retrieve source quotes:
1. Parse `source_id` fields from entities (contains `chunk-abc<SEP>chunk-def`)
2. Open `kv_store_text_chunks.json` per commune
3. Load chunk content from JSON

This file I/O happened during query execution, adding 500ms+ latency.

**Solution:**
Made chunks first-class graph citizens with `HAS_SOURCE` edges:

1. **Added ChunkMetadata dataclass** - stores full chunk content in memory
2. **Extended GraphIndex to load chunks** - `_load_commune_chunks()` runs during initialization
3. **Created HAS_SOURCE/SOURCED_BY edges** - bidirectional entity ↔ chunk links
4. **O(1) chunk retrieval** - `get_chunks_for_entity()` traverses edges, no file I/O

```python
# Before (file I/O during query - 500ms+)
chunk_requests = [(chunk_id, commune_id) for c in communities...]
source_quotes = await load_chunks_parallel(chunk_requests)

# After (in-memory traversal - <1ms)
for entity in entities:
    chunks = index.get_chunks_for_entity(entity_id)  # O(degree) lookup
    for chunk in chunks:
        source_quotes.append({
            "id": chunk.chunk_id,
            "content": chunk.content[:500],
            "commune": chunk.commune,
        })
```

**Memory Impact:**
- ~1,000 chunks × ~1.5KB = ~1.5 MB additional memory
- ~5,000 HAS_SOURCE edges × ~50 bytes = ~0.25 MB
- Total: ~1.75 MB (trivial for server)

**Performance Impact:**
| Operation | Before | After |
|-----------|--------|-------|
| Get chunks for query | 500ms (file I/O) | <1ms (in-memory) |
| Index load time | ~2s | ~3s (one-time) |

**Files changed:**
- `graph_index.py`: Added ChunkMetadata, _load_commune_chunks(), get_chunk(), get_chunks_for_entity()
- `server.py`: Updated grand_debat_query_fast() to use graph traversal

**Date fixed:** 2026-01-03

---

### Chunks Not Retrieved (expand_weighted Returns Chunks as Entities)

**Problem:**
```
source_quotes: 0
No citizen quotes in LLM context
meaning_match: 0.02 (very low)
```

**Symptoms:**
- `get_chunks_for_entity()` returns empty lists for all expanded entities
- Source quotes are 0 even though chunks exist in GraphIndex
- LLM responses don't include citizen text

**Root Cause:**
When `expand_weighted()` is called with `include_chunks=True`, it traverses to chunks and returns them as entities. These chunk pseudo-entities have IDs like `contrib-6e0daf98...`.

Chunks don't have `HAS_SOURCE` edges to other chunks - they ARE the sources. So `get_chunks_for_entity("contrib-xxx")` returns nothing.

```
Entity FISCALITÉ --[HAS_SOURCE]--> Chunk contrib-xxx
                                    ↑
                              expand_weighted returns this
                                    ↓
get_chunks_for_entity("contrib-xxx") -> [] (chunks don't have HAS_SOURCE)
```

**Solution:**
Get chunks from **seed entities** (like `FISCALITÉ`), not from expanded entities:

```python
# Before (broken): iterating over expanded entities which include chunks
for entity in entities[:100]:
    entity_id = entity.get('id', '')  # This is "contrib-xxx" (a chunk!)
    chunks = index.get_chunks_for_entity(entity_id)  # Returns []

# After (fixed): iterate over all_seeds (original entity IDs)
for seed_id in all_seeds[:100]:  # IDs like "FISCALITÉ", "CSG", etc.
    chunks = index.get_chunks_for_entity(seed_id)  # Returns chunks!
```

**Verification:**
```
Before: source_quotes: 0
After: source_quotes: 15
```

**Files changed:**
- `server.py`: Changed chunk retrieval loop from `entities` to `all_seeds`

**Date fixed:** 2026-01-03

---

### GraphML Structure Mismatch: source_id Attribute vs HAS_SOURCE Edges (0.15% Chunk Retrieval Success)

**Problem:**
```
Only 0.15% of queries successfully retrieve citizen text chunks (2 out of 1,318 traces)
GraphRAG responses focus on entity labels instead of chunk content
meaning_match scores remain very low (0.02) despite all previous fixes
```

**Symptoms:**
- Opik evaluation shows 99.85% of queries have empty source_quotes
- GraphRAG-Local returns entity labels like `EDUCATION_ET_SENSIBILISATION_DES_PLUS_JEUNES`
- GraphRAG-Global returns cluster IDs like `L0C0_C0_C0_C0` instead of citizen text
- `get_chunks_for_entity()` returns empty lists for virtually all entities
- High hallucination scores because LLM fabricates answers without source text

**Root Cause:**
The `get_chunks_for_entity()` function expected HAS_SOURCE edges in the GraphML files, but the actual GraphML structure stores chunk references in a `source_id` **attribute** within entity nodes:

```xml
<!-- Actual GraphML Structure -->
<node id="CSG">
  <data key="entity_type">REFORMEFISCALE</data>
  <data key="source_id">contrib-ad5d...958<SEP>contrib-6e0d...058</data>
  <!-- Chunks are in ATTRIBUTE, separated by <SEP> -->
</node>

<!-- What the code expected -->
<edge source="CSG" target="contrib-ad5d...958" type="HAS_SOURCE" />
```

Edge types present in GraphML:
- ✅ `FAIT_PARTIE_DE`
- ✅ `FAIT_REMONTER`
- ✅ `RELATED_TO`
- ❌ `HAS_SOURCE` (MISSING - stored as attribute instead!)

The code path:
1. `get_chunks_for_entity()` traverses `HAS_SOURCE` edges (lines 405-408)
2. GraphML has no such edges → function returns empty list
3. Server populates `source_quotes: []` in response
4. LLM receives only entity labels, no citizen text
5. Result: 99.85% failure rate

**Solution:**
Modified `get_chunks_for_entity()` to use the already-parsed `_entity_source_ids` dictionary instead of traversing non-existent edges:

```python
# Before (broken - traverses edges that don't exist)
def get_chunks_for_entity(self, entity_id: str) -> List[ChunkMetadata]:
    chunks = []
    for edge in self.get_neighbors(entity_id):
        if edge.rel_type == "HAS_SOURCE" and edge.target in self._chunks:
            chunks.append(self._chunks[edge.target])
    return chunks

# After (fixed - uses parsed source_id attribute)
def get_chunks_for_entity(self, entity_id: str) -> List[ChunkMetadata]:
    chunks = []
    # Use parsed source_ids from GraphML attributes (line 222-227)
    chunk_ids = self._entity_source_ids.get(entity_id, [])
    for chunk_id in chunk_ids:
        if chunk_id in self._chunks:
            chunks.append(self._chunks[chunk_id])
    return chunks
```

**Key Insight:**
The `source_id` attribute was already being parsed during GraphML loading (lines 222-227) and stored in `self._entity_source_ids`, but the retrieval function was looking in the wrong place (edges instead of the dictionary).

**Results:**
- **Before**: 0.15% success rate (2 / 1,318 queries)
- **After**: 93.7% coverage (15,279 / 16,302 entities have chunks)
- **Chunk distribution**:
  - 97.0% of entities: 1 chunk
  - 1.9% of entities: 2 chunks
  - 0.1% of entities: 3+ chunks
  - Maximum: 46 chunks for one entity

**Performance Impact:**
- Complexity remains O(1) - dictionary lookup instead of edge traversal
- No change to memory usage (data structure already existed)
- Expected meaning_match improvement: 0.02 → 0.60+ (30x increase)

**Files changed:**
- `graph_index.py`: Modified `get_chunks_for_entity()` (lines 391-410)

**Date fixed:** 2026-01-03
