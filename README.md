# Grand Debat National GraphRAG MCP Server

A remote MCP (Model Context Protocol) server that exposes GraphRAG capabilities for the **Grand Debat National** "Cahiers de Doleances" dataset.

## Live Endpoint

```
https://graphragmcp-production.up.railway.app/mcp
```

## Overview

This MCP server enables LLMs to query and analyze citizen contributions from the French Grand Debat National (2019). Each commune's "Cahier de Doleances" is indexed as a separate GraphRAG knowledge graph, allowing semantic search across 50 communes with 8,000+ entities.

### What is GraphRAG?

GraphRAG combines knowledge graphs with retrieval-augmented generation. Instead of simple vector search, it:
- Extracts **entities** (people, themes, concepts) and **relationships** from text
- Clusters related entities into **communities** with AI-generated summaries
- Enables both specific entity lookups and high-level thematic analysis

## Available Tools

| Tool | Description | Use Case |
|------|-------------|----------|
| `grand_debat_list_communes` | List all 50 communes with statistics | Discover available data |
| `grand_debat_query` | Query using GraphRAG (local/global mode) | Answer questions about citizen concerns |
| `grand_debat_search_entities` | Search entities by pattern | Find specific themes or actors |
| `grand_debat_get_communities` | Get community reports | Explore thematic clusters |
| `grand_debat_get_contributions` | Get sample contributions | Read original citizen texts |

### Query Modes

- **Local Mode**: Entity-based queries finding specific mentions and relationships. Best for targeted questions.
- **Global Mode**: Community-based summaries providing high-level themes. Best for broad overviews.

## Quick Start

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

# 3. Query a commune
curl -s -X POST "https://graphragmcp-production.up.railway.app/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: YOUR_SESSION_ID" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "grand_debat_query", "arguments": {"params": {"commune_id": "Rochefort", "query": "Quelles sont les principales preoccupations fiscales?", "mode": "local"}}}, "id": 3}'
```

### Configure in Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json`:

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

### Configure in Cline / VS Code

Add to your MCP settings:

```json
{
  "grand-debat": {
    "url": "https://graphragmcp-production.up.railway.app/mcp",
    "transport": "streamable-http"
  }
}
```

### Configure in Dust.tt

Dust.tt supports remote MCP servers natively. See [Dust Remote MCP Server docs](https://docs.dust.tt/docs/remote-mcp-server).

**Setup steps:**

1. Go to **Dust Admin** → **Developers** → **MCP Servers**
2. Click **Add Remote Server**
3. Enter the server URL:
   ```
   https://graphragmcp-production.up.railway.app/mcp
   ```
4. Give it a name (e.g., "Grand Debat GraphRAG")
5. Click **Sync** - Dust will discover all 5 tools automatically
6. Assign the server to your desired **Spaces**

**Using in Dust Agents:**

Once configured, your Dust agents can use the tools directly:

```
@agent Query the Grand Debat data for Rochefort about fiscal concerns
```

The agent will automatically:
- Initialize a session with the MCP server
- Call `grand_debat_query` with appropriate parameters
- Return the GraphRAG-powered response

**Authentication (Optional):**

The server is currently public. To add authentication:
- In Dust, add a **Bearer Token** under server settings
- The token will be sent as `Authorization: Bearer <token>` header

**Available Tools in Dust:**

| Tool | What Dust Agents Can Do |
|------|------------------------|
| `grand_debat_list_communes` | Discover available communes and statistics |
| `grand_debat_query` | Answer questions using GraphRAG |
| `grand_debat_search_entities` | Find specific themes, actors, concepts |
| `grand_debat_get_communities` | Get AI-generated thematic summaries |
| `grand_debat_get_contributions` | Read original citizen texts |

## Example Queries

### List Communes

```json
{
  "name": "grand_debat_list_communes",
  "arguments": {}
}
```

Returns 50 communes including: Rochefort (812 entities), Marennes_Hiers_Brouage (659 entities), Saint_Xandre (537 entities), Saint_Jean_Dangely (505 entities), etc.

### Query with Local Mode (Entity-based)

```json
{
  "name": "grand_debat_query",
  "arguments": {
    "params": {
      "commune_id": "Rochefort",
      "query": "Quelles sont les principales preoccupations fiscales des citoyens?",
      "mode": "local"
    }
  }
}
```

### Query with Global Mode (Community-based)

```json
{
  "name": "grand_debat_query",
  "arguments": {
    "params": {
      "commune_id": "Surgeres",
      "query": "Quels sont les grands themes abordes par les citoyens?",
      "mode": "global"
    }
  }
}
```

### Search Entities

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

### Get Community Reports

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

### Get Original Contributions

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

## Available Communes

The server includes data from 50 communes in Charente-Maritime:

| Commune | Entities | Communities | Contributions |
|---------|----------|-------------|---------------|
| Rochefort | 812 | 140 | 102 |
| Marennes_Hiers_Brouage | 659 | 119 | 52 |
| Saint_Xandre | 537 | 78 | 41 |
| Saint_Jean_Dangely | 505 | 0 | 50 |
| Rivedoux_Plage | 387 | 56 | 28 |
| U_Gue_Dallere | 356 | 17 | 21 |
| Surgeres | 330 | 54 | 26 |
| ... | ... | ... | ... |

## Local Development

### Prerequisites

- Python 3.11+
- OpenAI API key

### Setup

```bash
# Clone repository
git clone https://github.com/ArthurSrz/graphRAGmcp.git
cd graphRAGmcp

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-api-key"
export GRAND_DEBAT_DATA_PATH="./law_data"

# Run with stdio (for local MCP testing)
python server.py --stdio

# Run as HTTP server
python server.py --port 8000
```

### Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python server.py --stdio
```

## Deployment

### Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Set environment variable
railway variables --set "OPENAI_API_KEY=your-key"

# Deploy
railway up
```

### Deploy to Cloud Run

```bash
gcloud run deploy grand-debat-mcp \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-env-vars "OPENAI_API_KEY=your-key"
```

### Docker

```bash
# Build
docker build -t grand-debat-mcp .

# Run
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="your-key" \
  grand-debat-mcp
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for GraphRAG queries | **Required** |
| `GRAND_DEBAT_DATA_PATH` | Path to commune data | `./law_data` |
| `PORT` | HTTP server port | `8080` |

## Architecture

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
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      OpenAI API                             │
│              (GPT-4o-mini for query synthesis)              │
└─────────────────────────────────────────────────────────────┘
```

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

## MCP Protocol Details

### Required Headers

```
Content-Type: application/json
Accept: application/json, text/event-stream
mcp-session-id: <session-id-from-init>  # Required after initialization
```

### Session Flow

1. **Initialize**: Get session ID from response headers
2. **Call tools**: Include session ID in subsequent requests
3. **Handle SSE**: Responses are Server-Sent Events with `event: message` and `data: {...}`

## Troubleshooting

### "Invalid Host header" (421)

The MCP SDK has DNS rebinding protection. For proxy deployments, ensure `TransportSecuritySettings` is configured:

```python
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)
```

### "No module named X"

Ensure all dependencies are installed. Key packages:
- `mcp>=1.0.0`
- `uvicorn>=0.30.0`
- `nano-vectordb>=0.0.4`
- `hnswlib>=0.7.0` (requires g++ for compilation)

### Query returns empty results

- Check if the commune exists: use `grand_debat_list_communes`
- Verify commune_id matches exactly (e.g., `Saint_Jean_Dangely` not `Saint-Jean-d'Angely`)

See [troubleshooting.md](troubleshooting.md) for detailed solutions.

## License

MIT
