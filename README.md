# GraphRAG MCP Server: Production-Grade Knowledge Graph Retrieval for LLMs

A remote MCP (Model Context Protocol) server delivering graph-powered semantic search over the **Grand Débat National** dataset. Query 50 communes with 8,000+ entities using graph-first architecture that's **29x faster than vector RAG** with built-in provenance tracing every answer back to citizen contributions.

**Live Endpoint (No signup required)**:
```
https://graphragmcp-production.up.railway.app/mcp
```

---

## What Makes This Special

This isn't just another RAG system. GraphRAG MCP Server is built on seven constitutional principles that deliver measurable advantages in speed, transparency, and quality.

### 1. Lightning-Fast Graph Traversal

**For users**: Queries return in 1-2 seconds, not 30-60 seconds. Interactive experiences, real-time analysis.

**How we do it**: Pre-computed graph indices loaded at startup enable O(1) neighbor lookups. No per-query graph parsing.

**Evidence**: **50x performance improvement** documented in [troubleshooting.md](troubleshooting.md) — graph loading time reduced from 25-30 seconds per query to 0.5 seconds. Compared to traditional vector RAG, GraphRAG achieves **29x faster response times** (1.3s mean latency vs 45s, measured across 54 queries in [experimental evaluation](docs/eval/experimental-design-rag-comparison.md)).

---

### 2. No Orphan Nodes - Everything Connects

**For users**: Every piece of information is contextualized through relationships. You get richer context, better answers, no isolated facts.

**How we do it**: Commune-centric design where every entity tracks its source commune and connections. Graph operations only return entities with relationships — orphan nodes are automatically filtered.

**Why it matters**: Information without context is just noise. The graph structure ensures that when you ask about taxation concerns, you don't just get a keyword match — you get themes, related concepts, and the citizen contributions that discuss them together.

---

### 3. Complete Transparency - Answer Provenance

**For users**: See exactly which citizen contributions support each claim. Verify accuracy, build trust, audit responses.

**How we do it**: Text chunks are first-class graph nodes with bidirectional edges to entities. Every response includes source quotes traceable through the graph: `chunk → entity → response`.

**Evidence**: Chunk retrieval optimization reduced file I/O from **500ms+ to <1ms** by treating chunks as graph entities with in-memory traversal ([troubleshooting.md](troubleshooting.md) - "Fast Graph Traversal to Chunks"). After the GraphML source_id attribute discovery, **93.7% of entities** now have retrievable source chunks (up from 0.15%) ([constitution.md](.specify/memory/constitution.md)).

---

### 4. Universal MCP Compatibility

**For users**: Works with Claude Desktop, Cline, Dust.tt, any MCP client. Integrate once, use everywhere.

**How we do it**: Flat parameter signatures (not nested Pydantic models), JSON-RPC 2.0 compliance, Server-Sent Events for streaming. Tested with multiple clients.

**Why it matters**: The "Pydantic Validation Error" issue documented in [troubleshooting.md](troubleshooting.md) shows that nested params break Dust.tt compatibility. Flat parameters ensure this server works universally without client-specific workarounds.

---

### 5. Performance by Design

**For users**: Every optimization is documented with before/after metrics. No mystery performance regressions, complete architectural transparency.

**Evidence**: [troubleshooting.md](troubleshooting.md) documents **7 major optimization efforts** with quantified improvements:
- Pre-computed graph indices: **50x speedup**
- Dual-strategy retrieval: **16% → 92.7% corpus coverage**
- Fast chunk traversal: **500ms → <1ms**
- LLM cache singleton: **-5-20s for overlapping queries**

---

### 6. Empirically Validated Quality

**For users**: Changes are tested with LLM-as-judge, not gut feelings. Confidence that updates improve quality.

**How we do it**: OPIK evaluation framework with GPT-4o-mini judge measuring meaning_match, hallucination, answer_relevance, and latency. A/B comparisons control for model, temperature, timeout, and execution order.

**Evidence**: The experimental-design-rag-comparison.md evaluation revealed the 9-commune limitation bug (meaning_match: 0.037 → 0.60+ after fix). Systematic testing with **100% success rate** (54/54 queries) and **lower hallucination** than vector RAG (0.25 vs 0.54) validates production-readiness.

---

### 7. Architecture Through Iteration

**For users**: System evolved through real-world problem solving, not ivory tower design. Battle-tested architecture.

**Example**: The GraphML `source_id` attribute discovery emerged from debugging why 99.85% of chunk retrievals were failing. Investigation revealed chunks weren't connected via `HAS_SOURCE` edges as expected, but through a semicolon-separated `source_id` attribute. This architectural insight (documented in [troubleshooting.md](troubleshooting.md)) fundamentally changed how chunks are accessed, improving coverage from **0.15% to 93.7%**.

---

## Quick Start - Get Running in 5 Minutes

### Test with curl

```bash
# 1. Initialize session
curl -s -i -X POST "https://graphragmcp-production.up.railway.app/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}, "id": 1}'

# Note the mcp-session-id header in response

# 2. List available communes
curl -s -X POST "https://graphragmcp-production.up.railway.app/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: YOUR_SESSION_ID" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "grand_debat_list_communes", "arguments": {}}, "id": 2}'

# 3. Run your first query
curl -s -X POST "https://graphragmcp-production.up.railway.app/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: YOUR_SESSION_ID" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "grand_debat_query", "arguments": {"params": {"commune_id": "Rochefort", "query": "Quelles sont les principales préoccupations fiscales?", "mode": "local"}}}, "id": 3}'
```

### Configure in Your MCP Client

- **Claude Desktop** → See [Section 5.1](#51-claude-desktop)
- **Cline / VS Code** → See [Section 5.2](#52-cline--vs-code)
- **Dust.tt** → See [Section 5.3](#53-dusttt)
- **Custom MCP Client** → See [Section 5.4](#54-custom-mcp-clients)

---

## Understanding the Dataset

### What is the Grand Débat National?

The **Grand Débat National** (2019) was a French civic consultation initiative where citizens contributed to "Cahiers de Doléances" — notebooks documenting concerns, proposals, and perspectives on public policy. This server indexes citizen contributions from **50 communes in Charente-Maritime**, creating a unique civic research tool.

### Coverage & Structure

- **Geographic scope**: 50 communes in Charente-Maritime département, France
- **Total entities**: 8,000+ extracted concepts, themes, policy proposals
- **Structure**: Each commune is a separate knowledge graph
- **Entity types** (extracted from citizen contributions in French):
  - **PROPOSITION** (policy proposals/suggestions)
  - **THEMATIQUE** (thematic categories)
  - **SERVICEPUBLIC** (public services)
  - **DOLEANCE** (grievances/complaints)
  - **CONCEPT** (conceptual entities)
  - **OPINION** (citizen opinions/viewpoints)
  - **ACTEURINSTITUTIONNEL** (institutional actors)
  - **CITOYEN** (citizen references)
  - Plus others: REFORMEDEMOCRATIQUE (democratic reforms), TERRITOIRE (territories), CONSULTATION (consultations), VERBATIM (direct quotes), CLUSTERSEMANTIQUE (semantic clusters), TYPEIMPOT (tax types), REFORMEFISCALE (fiscal reforms), MESUREECOLOGIQUE (ecological measures), etc.
- **Relationships**: **RELATED_TO** (semantic connections between entities)

### Top Communes by Coverage

| Commune | Entities | Communities | Contributions |
|---------|----------|-------------|---------------|
| Rochefort | 812 | 140 | 102 |
| Marennes_Hiers_Brouage | 659 | 119 | 52 |
| Saint_Xandre | 537 | 78 | 41 |
| Saint_Jean_Dangely | 505 | 0 | 50 |
| Rivedoux_Plage | 387 | 56 | 28 |
| L_Gue_Dallere | 356 | 17 | 21 |
| Surgères | 330 | 54 | 26 |

**Use Cases**: Civic research, policy analysis, democratic participation studies, thematic analysis of citizen concerns (taxation, public services, environmental issues, democratic participation).

---

## Integration Guides

### 5.1 Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json` (macOS/Linux) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "grand-debat": {
      "url": "https://graphragmcp-production.up.railway.app/mcp",
      "transport": "streamable-http"
    }
  }
}
```

**Restart Claude Desktop**. Verify tools appear in the MCP tools list (hammer icon).

---

### 5.2 Cline / VS Code

Add to your MCP settings (`.vscode/mcp.json` or Cline extension settings):

```json
{
  "grand-debat": {
    "url": "https://graphragmcp-production.up.railway.app/mcp",
    "transport": "streamable-http"
  }
}
```

**Reload VS Code window**. Verify tools appear in Cline's tool panel.

---

### 5.3 Dust.tt

Dust.tt supports remote MCP servers natively. See [Dust Remote MCP Server docs](https://docs.dust.tt/docs/remote-mcp-server).

**Setup steps**:

1. Go to **Dust Admin** → **Developers** → **MCP Servers**
2. Click **Add Remote Server**
3. Enter server URL: `https://graphragmcp-production.up.railway.app/mcp`
4. Give it a name (e.g., "Grand Debat GraphRAG")
5. Click **Sync** — Dust will discover all 5 tools automatically
6. Assign the server to your desired **Spaces**

**Using in Dust Agents**:

```
@agent Query the Grand Debat data for Rochefort about fiscal concerns
```

The agent will automatically initialize a session, call `grand_debat_query`, and return the GraphRAG-powered response.

---

### 5.4 Custom MCP Clients

**Requirements**: JSON-RPC 2.0 over HTTP, Server-Sent Events (SSE) for streaming responses.

**Session Flow**:

1. **Initialize**: `POST /mcp` with `initialize` method → receive `mcp-session-id` in response headers
2. **Call tools**: `POST /mcp` with `tools/call` method, include `mcp-session-id` header
3. **Parse SSE**: Responses are `event: message` with `data: {...}` containing JSON-RPC result

**Example (Python)**:

```python
import httpx

session = httpx.Client(base_url="https://graphragmcp-production.up.railway.app")

# Initialize
resp = session.post("/mcp", json={
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "custom", "version": "1.0"}},
    "id": 1
}, headers={"Accept": "application/json, text/event-stream"})

session_id = resp.headers["mcp-session-id"]

# Call tool
resp = session.post("/mcp", json={
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {"name": "grand_debat_list_communes", "arguments": {}},
    "id": 2
}, headers={"mcp-session-id": session_id, "Accept": "application/json, text/event-stream"})

print(resp.text)  # Parse SSE response
```

---

## MCP Tools Reference

### 6.1 Which Tool Should I Use?

```
Want to see what's available?
  ↓
  grand_debat_list_communes

Have a specific question about a commune?
  ↓
  grand_debat_query (mode: "local")

Need a thematic overview?
  ↓
  grand_debat_query (mode: "global")

Looking for specific entities/themes?
  ↓
  grand_debat_search_entities

Want to explore topic clusters?
  ↓
  grand_debat_get_communities

Need to read original citizen texts?
  ↓
  grand_debat_get_contributions
```

---

### 6.2 Tool Details

#### `grand_debat_list_communes`

**Purpose**: Discover all 50 available communes with statistics (entity counts, community counts, contribution counts).

**When to use**: First step to understand dataset coverage, or to get exact commune IDs for queries.

**Parameters**: None

**Returns**: Array of commune objects with `name`, `total_entities`, `total_communities`, `total_contributions`.

**Example**:

```json
{
  "name": "grand_debat_list_communes",
  "arguments": {}
}
```

**Response**:
```json
{
  "communes": [
    {"name": "Rochefort", "total_entities": 812, "total_communities": 140, "total_contributions": 102},
    {"name": "Marennes_Hiers_Brouage", "total_entities": 659, "total_communities": 119, "total_contributions": 52},
    ...
  ]
}
```

---

#### `grand_debat_query`

**Purpose**: Main query tool — answer questions using GraphRAG with local (entity-based) or global (community-based) modes.

**When to use**: This is your primary tool for answering questions about citizen concerns. Use **local mode** for targeted fact-finding, **global mode** for thematic overviews.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `commune_id` | string | Yes | Exact commune name (use `grand_debat_list_communes` to get valid IDs) |
| `query` | string | Yes | Natural language question (French recommended for this dataset) |
| `mode` | string | Yes | `"local"` (entity-based) or `"global"` (community-based) |

**Returns**: Structured response with `answer` (synthesized answer), `sources` (entity names or community reports), `provenance` (source chunks with quotes).

**Example (Local Mode)**:

```json
{
  "name": "grand_debat_query",
  "arguments": {
    "params": {
      "commune_id": "Rochefort",
      "query": "Quelles sont les principales préoccupations fiscales des citoyens?",
      "mode": "local"
    }
  }
}
```

**Example (Global Mode)**:

```json
{
  "name": "grand_debat_query",
  "arguments": {
    "params": {
      "commune_id": "Surgères",
      "query": "Quels sont les grands thèmes abordés par les citoyens?",
      "mode": "global"
    }
  }
}
```

**Tips**:
- Use exact commune IDs from `grand_debat_list_communes` (e.g., `Saint_Jean_Dangely` not `Saint-Jean-d'Angély`)
- Local mode finds specific entities → traverses graph → retrieves source chunks (~1-2s)
- Global mode uses AI-generated community summaries → faster for broad themes (~1-3s)

---

#### `grand_debat_search_entities`

**Purpose**: Search for entities (themes, concepts, actors) matching a keyword pattern.

**When to use**: When you need to find specific topics mentioned in the data without asking a full question.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `commune_id` | string | Yes | Commune to search within |
| `pattern` | string | Yes | Keyword or phrase to match (case-insensitive, partial match) |
| `limit` | integer | No | Max results to return (default: 20) |

**Returns**: Array of entities with `entity_name`, `entity_type`, `description`.

**Example**:

```json
{
  "name": "grand_debat_search_entities",
  "arguments": {
    "params": {
      "commune_id": "Marans",
      "pattern": "retraite",
      "limit": 20
    }
  }
}
```

---

#### `grand_debat_get_communities`

**Purpose**: Retrieve AI-generated thematic community reports (Louvain algorithm clustering).

**When to use**: Explore how the GraphRAG system has organized entities into topic clusters.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `commune_id` | string | Yes | Commune to retrieve communities from |
| `limit` | integer | No | Max communities to return (default: 10) |

**Returns**: Array of community objects with `level`, `title`, `summary`, `rank`, `findings`.

**Example**:

```json
{
  "name": "grand_debat_get_communities",
  "arguments": {
    "params": {
      "commune_id": "Rivedoux_Plage",
      "limit": 10
    }
  }
}
```

---

#### `grand_debat_get_contributions`

**Purpose**: Get original citizen contribution texts (source documents).

**When to use**: Read raw citizen input, verify quotes, understand context beyond extracted entities.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `commune_id` | string | Yes | Commune to retrieve contributions from |
| `limit` | integer | No | Max contributions to return (default: 5) |

**Returns**: Array of contribution objects with `full_doc_id`, `content`, `commune`, `tokens`, `chunk_order_index`.

**Example**:

```json
{
  "name": "grand_debat_get_contributions",
  "arguments": {
    "params": {
      "commune_id": "Andilly",
      "limit": 5
    }
  }
}
```

---

## Query Modes Explained

### 7.1 Local Mode - Entity-Based Retrieval

**What it does**: Finds specific entities matching your query, traverses the graph to find related entities and relationships, retrieves source chunks via graph edges, synthesizes answer with LLM using context.

**Best for**:
- Targeted questions ("What do citizens say about pensions?")
- Fact-finding ("Are there concerns about fiscal policy?")
- Specific topics ("Mentions of environmental issues")

**How it works**: Keyword matching → graph expansion via weighted Dijkstra → chunk retrieval via `source_id` attribute → LLM synthesis with provenance.

**Performance**: ~1-2 seconds (graph traversal is <1ms, LLM call is majority of latency).

**Example questions**:
- "Quelles sont les préoccupations fiscales à Rochefort?"
- "Que disent les citoyens sur les retraites?"
- "Mentions de la transition écologique?"

---

### 7.2 Global Mode - Community-Based Analysis

**What it does**: Selects relevant community reports (AI-generated thematic summaries), combines community summaries as context, synthesizes high-level overview with LLM.

**Best for**:
- Broad overviews ("What are the main themes?")
- Thematic patterns ("Overview of citizen concerns")
- Multi-topic analysis ("What topics are discussed together?")

**How it works**: Community selection via keyword matching → report retrieval (pre-generated) → LLM synthesis with thematic context.

**Performance**: ~1-3 seconds (slightly slower due to larger context from community summaries).

**Example questions**:
- "Quels sont les grands thèmes du débat?"
- "Vue d'ensemble des préoccupations citoyennes?"
- "Thématiques principales abordées?"

---

### 7.3 Choosing the Right Mode

| Question Type | Mode | Reason |
|--------------|------|--------|
| Specific facts | Local | Direct entity retrieval with provenance |
| Thematic overview | Global | Community summaries provide high-level patterns |
| Multi-commune | Local | Cross-graph traversal (set `commune_id` to null or query all) |
| Exploratory | Global | Higher-level patterns without drilling into specifics |
| Provenance-critical | Local | Full chunk→entity→response tracing |

---

## Performance & Quality

### 8.1 Benchmarked Performance

**Latency**: **1.3s mean** vs **45s for vector RAG** — **29x faster** ([experimental-design-rag-comparison.md](docs/eval/experimental-design-rag-comparison.md))

**Reliability**: **100% success rate** (54/54 queries successful in evaluation)

**Coverage**: **92.7% corpus coverage** with dual-strategy retrieval (up from 16% with single-strategy)

**Provenance**: **93.7% of entities** have retrievable source chunks (up from 0.15% after GraphML source_id discovery)

---

### 8.2 Quality Validation

**Framework**: OPIK evaluation platform with GPT-4o-mini as LLM judge (temperature=0 for consistency).

**Metrics**:
- `meaning_match`: Semantic equivalence between response and expected answer
- `hallucination`: Inverted faithfulness score (1 = faithful, 0 = hallucinated)
- `answer_relevance`: How directly response addresses question
- `usefulness`: Practical utility for answering civic questions

**Results** (from experimental-design-rag-comparison.md):
- GraphRAG: **Lower hallucination rate** than vector RAG (0.25 vs 0.54)
- GraphRAG: **Equivalent semantic precision** to vector RAG (0.30 LLM precision score)
- GraphRAG: **35x faster** latency while maintaining quality

---

### 8.3 Key Optimizations

Brief summary with links to [troubleshooting.md](troubleshooting.md):

1. **Pre-computed graph indices**: **50x speedup** (25-30s → 0.5s per query) by loading all commune graphs at startup into in-memory adjacency lists
2. **Dual-strategy retrieval**: **16% → 92.7% coverage** by combining community keywords + global entity search for cross-commune queries
3. **Fast chunk traversal**: **500ms+ file I/O → <1ms in-memory** by treating chunks as graph entities with bidirectional edges
4. **GraphML source_id fix**: **0.15% → 93.7% success rate** by discovering chunks are connected via `source_id` attribute (not `HAS_SOURCE` edges)
5. **LLM cache singleton**: **-5-20s for overlapping queries** by preventing redundant cache initialization per request
6. **Weighted graph traversal**: Prioritizes semantic relationships (CONCERNE: 1.0) over structural relationships (RELATED_TO: 0.1) using Dijkstra's algorithm
7. **DNS rebinding protection fix**: Resolves HTTP 421 errors on Railway/Cloud Run by disabling MCP SDK's DNS rebinding check (proxy handles security)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   MCP Client (Claude, Cline, etc.)          │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Streamable HTTP / MCP Protocol
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Grand Debat MCP Server (Railway)               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ FastMCP + Uvicorn                                    │  │
│  │                                                       │  │
│  │ Tools:                                                │  │
│  │  - grand_debat_list_communes                         │  │
│  │  - grand_debat_query (local/global)                  │  │
│  │  - grand_debat_search_entities                       │  │
│  │  - grand_debat_get_communities                       │  │
│  │  - grand_debat_get_contributions                     │  │
│  │                                                       │  │
│  │ GraphIndex (in-memory adjacency lists)               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    nano_graphrag Engine                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Entities  │  │ Communities │  │   Text Chunks       │ │
│  │   (VDB)     │  │  (Reports)  │  │ (Contributions)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Knowledge Graph (GraphML)               │   │
│  │   Entities ──relationships──> Entities               │   │
│  │   Chunks connected via source_id attribute           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      OpenAI API                             │
│              (GPT-4o-mini for query synthesis)              │
└─────────────────────────────────────────────────────────────┘
```

### Components

- **FastMCP + Uvicorn**: MCP protocol server with TransportSecuritySettings for reverse proxy compatibility
- **GraphIndex**: Pre-computed graph indices (feature 007) enabling O(1) neighbor lookups, loaded at server startup
- **nano_graphrag**: Graph traversal and query engine with dual-strategy retrieval
- **Storage**: GraphML graphs (entity relationships), JSON stores (chunks, community reports, entity vectors)
- **LLM**: GPT-4o-mini for query synthesis and community report generation

### Data Flow

1. **Client initializes MCP session** → receives `mcp-session-id`
2. **Tool call dispatched** (e.g., `grand_debat_query`) with session ID
3. **GraphIndex retrieves entities** via O(1) adjacency list lookups
4. **Graph traversal** finds related entities/chunks using weighted Dijkstra
5. **Context assembled** from chunks (via `source_id` attribute) + community reports
6. **LLM synthesizes answer** with source quotes and provenance chains
7. **Response streamed** via Server-Sent Events (SSE)

### Key Architectural Decisions

- **Pre-computation**: All 50 commune graphs loaded at startup (no lazy loading) to guarantee O(1) lookups
- **Graph-first**: Chunks are graph nodes, provenance is graph edges (bidirectional chunk↔entity connections)
- **Weighted traversal**: Dijkstra's algorithm with relationship type weights (CONCERNE: 1.0, HAS_SOURCE: 0.9, APPARTIENT_A: 0.3, RELATED_TO: 0.1)
- **Dual-strategy**: For cross-commune queries, combine community keywords + global entity search to achieve 92.7% coverage

---

## Data Structure

Each commune folder contains pre-indexed GraphRAG data:

```
law_data/
├── Rochefort/
│   ├── vdb_entities.json              # Entity vector database
│   ├── kv_store_text_chunks.json      # Original contribution texts
│   ├── kv_store_community_reports.json # AI-generated community summaries
│   ├── kv_store_full_docs.json        # Full documents
│   ├── kv_store_llm_response_cache.json # Cached LLM responses
│   └── graph_chunk_entity_relation.graphml # Knowledge graph
├── Andilly/
│   └── ...
└── ... (50 communes total)
```

### GraphML Schema

**Nodes**:
- `entity_name`: Entity identifier (unique per commune)
- `entity_type`: COMMUNE, CONCEPT, THEME, CITIZEN_CONTRIBUTION, CHUNK
- `description`: Natural language description
- `source_id`: **Critical attribute** — semicolon-separated chunk IDs (e.g., "chunk_001<SEP>chunk_002")

**Edges**:
- `relationship_type` or `type`: CONCERNE, HAS_SOURCE, APPARTIENT_A, RELATED_TO
- `weight`: Relationship strength (optional)

**Chunks**: Connected via `source_id` attribute (NOT via `HAS_SOURCE` edges — this was a key discovery documented in troubleshooting.md).

---

## Deployment

### Environment Variables

| Variable | Description | Required | Default | Example |
|----------|-------------|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | Yes | - | `sk-...` |
| `GRAND_DEBAT_DATA_PATH` | Path to commune data directory | No | `./law_data` | `/data/communes` |
| `PORT` | HTTP server port | No | `8080` | `8000` |
| `ENABLE_OPIK_LOGGING` | Enable evaluation logging | No | `true` | `false` |
| `OPIK_API_KEY` | Opik API key for logging (optional) | No | - | `...` |

---

### Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Set environment variables
railway variables --set "OPENAI_API_KEY=your-key"

# Deploy
railway up
```

**Important**: Railway uses a reverse proxy (`railway-edge`). The server includes `TransportSecuritySettings(enable_dns_rebinding_protection=False)` to prevent HTTP 421 "Invalid Host header" errors (see [troubleshooting.md](troubleshooting.md)).

---

### Deploy to Cloud Run

```bash
gcloud run deploy grand-debat-mcp \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-env-vars "OPENAI_API_KEY=your-key"
```

---

### Docker

```bash
# Build
docker build -t grand-debat-mcp .

# Run
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="your-key" \
  -v $(pwd)/law_data:/app/law_data \
  grand-debat-mcp
```

---

### Local Development

**Prerequisites**: Python 3.11+, OpenAI API key

```bash
# Clone repository
git clone https://github.com/ArthurSrz/graphRAGmcp.git
cd graphRAGmcp

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-api-key"
export GRAND_DEBAT_DATA_PATH="./law_data"

# Run with stdio (for MCP Inspector testing)
python server.py --stdio

# Run as HTTP server
python server.py --port 8000
```

**Test with MCP Inspector**:

```bash
npx @modelcontextprotocol/inspector python server.py --stdio
```

---

## Troubleshooting

### Common Issues

#### 1. "Invalid Host header" (HTTP 421)

**Cause**: MCP SDK's DNS rebinding protection rejects requests from reverse proxies (Railway, Cloud Run) where the Host header doesn't match allowed list.

**Solution**: The server includes `TransportSecuritySettings(enable_dns_rebinding_protection=False)` — security is handled at the proxy layer. If you're running a custom deployment, ensure this setting is present in `server.py`.

---

#### 2. "Field required" Pydantic Validation Errors

**Cause**: Nested Pydantic models break Dust.tt and other MCP clients that expect flat parameter schemas.

**Solution**: This server uses flat parameters with `Annotated[type, Field(description="...")]` for universal client compatibility. If you're modifying tools, avoid nested params.

---

#### 3. Empty Query Results

**Cause**: Commune ID mismatch (e.g., using `Saint-Jean-d'Angély` instead of `Saint_Jean_Dangely`).

**Solution**: Always use `grand_debat_list_communes` to get exact commune IDs. The response includes the correct underscore-formatted names.

---

#### 4. Session Errors

**Cause**: Missing `mcp-session-id` header in tool calls.

**Solution**:
1. Call `initialize` method first → extract `mcp-session-id` from response headers
2. Include `mcp-session-id: <your-session-id>` header in all subsequent `tools/call` requests

---

#### 5. Slow First Query

**Cause**: First query after server startup warms caches (LLM response cache initialization, entity vector loading).

**Solution**: Expected behavior — subsequent queries are faster (~1-2s). This is a one-time cost per server restart.

---

**For detailed troubleshooting**, see [troubleshooting.md](troubleshooting.md) which documents all major optimizations, bug fixes, and architectural discoveries.

---

## Example Queries

### Discovery

**List all communes**:
```json
{"name": "grand_debat_list_communes", "arguments": {}}
```

**Search for retirement-related entities**:
```json
{
  "name": "grand_debat_search_entities",
  "arguments": {"params": {"commune_id": "Marans", "pattern": "retraite", "limit": 20}}
}
```

---

### Targeted Research (Local Mode)

**Fiscal concerns in Rochefort**:
```json
{
  "name": "grand_debat_query",
  "arguments": {"params": {"commune_id": "Rochefort", "query": "Quelles sont les principales préoccupations fiscales des citoyens?", "mode": "local"}}
}
```

**Retirement topics**:
```json
{
  "name": "grand_debat_query",
  "arguments": {"params": {"commune_id": "Saint_Xandre", "query": "Que disent les citoyens sur les retraites?", "mode": "local"}}
}
```

---

### Thematic Analysis (Global Mode)

**Overall themes in Surgères**:
```json
{
  "name": "grand_debat_query",
  "arguments": {"params": {"commune_id": "Surgères", "query": "Quels sont les grands thèmes abordés par les citoyens?", "mode": "global"}}
}
```

**Community clusters in Rivedoux-Plage**:
```json
{
  "name": "grand_debat_get_communities",
  "arguments": {"params": {"commune_id": "Rivedoux_Plage", "limit": 10}}
}
```

---

### Provenance & Verification

**Get original contributions from Andilly**:
```json
{
  "name": "grand_debat_get_contributions",
  "arguments": {"params": {"commune_id": "Andilly", "limit": 5}}
}
```

**Query with full provenance tracing** (Local mode automatically includes source chunks with quotes):
```json
{
  "name": "grand_debat_query",
  "arguments": {"params": {"commune_id": "Rochefort", "query": "Préoccupations environnementales?", "mode": "local"}}
}
```

---

## Contributing & Support

### Questions & Bug Reports

- **GitHub Issues**: Report bugs, request features → [github.com/ArthurSrz/graphRAGmcp/issues](https://github.com/ArthurSrz/graphRAGmcp/issues)
- **GitHub Discussions**: Ask questions, share use cases → [github.com/ArthurSrz/graphRAGmcp/discussions](https://github.com/ArthurSrz/graphRAGmcp/discussions)

### Performance Feedback

- Report performance regressions with benchmarks (before/after latency measurements)
- Performance improvements should include quantified impact (see [troubleshooting.md](troubleshooting.md) for template)

### Documentation Improvements

- Corrections and clarifications welcome via Pull Requests
- Focus on user-facing documentation (integration guides, examples, troubleshooting)

---

## Links & Resources

- **MCP Protocol Documentation**: [https://modelcontextprotocol.io](https://modelcontextprotocol.io)
- **Grand Débat National Background**: [https://granddebat.fr](https://granddebat.fr)
- **OPIK Evaluation Dashboard**: [https://www.comet.com/opik](https://www.comet.com/opik)
- **Experimental Evaluation Report**: [docs/eval/experimental-design-rag-comparison.md](docs/eval/experimental-design-rag-comparison.md)
- **Troubleshooting & Optimization History**: [troubleshooting.md](troubleshooting.md)
- **GraphIndex Implementation**: [graph_index.py](graph_index.py)
- **Constitutional Principles (Full Version)**: [.specify/memory/constitution.md](.specify/memory/constitution.md)

---

## License

MIT
