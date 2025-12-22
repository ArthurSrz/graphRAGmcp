# Grand Débat National GraphRAG MCP Server

A remote MCP (Model Context Protocol) server that exposes GraphRAG capabilities for the **Grand Débat National** "Cahiers de Doléances" dataset.

## Overview

This MCP server enables LLMs (including Dust.tt agents) to query and analyze citizen contributions from the French Grand Débat National (2019). Each commune's "Cahier de Doléances" is indexed as a separate GraphRAG knowledge graph.

## Features

### Available Tools

| Tool | Description |
|------|-------------|
| `grand_debat_list_communes` | List all available communes with statistics |
| `grand_debat_query` | Query a commune using GraphRAG (local/global mode) |
| `grand_debat_search_entities` | Search for entities by pattern |
| `grand_debat_get_communities` | Get community reports (thematic clusters) |
| `grand_debat_get_contributions` | Get sample citizen contributions |

### Query Modes

- **Local Mode**: Entity-based queries that find specific mentions and relationships
- **Global Mode**: Community-based summaries that provide high-level themes

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-api-key"
export GRAND_DEBAT_DATA_PATH="./law_data"

# Run with stdio (for local testing)
python server.py --stdio

# Run as HTTP server
python server.py --port 8000
```

### Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python server.py --stdio
```

## Deployment

### Public Endpoint (Railway)

The server is deployed and publicly accessible at:

```
https://graphragmcp-production.up.railway.app/mcp
```

**Test the endpoint:**

```bash
curl -X POST "https://graphragmcp-production.up.railway.app/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}, "id": 1}'
```

### Deploy to Railway

```bash
# Link project
railway link -p your-project-name

# Deploy
railway up
```

### Deploy to Cloud Run

```bash
# Build and deploy
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
  -e GRAND_DEBAT_DATA_PATH="/data" \
  -v /path/to/law_data:/data \
  grand-debat-mcp
```

## Configuration for Dust.tt

Use the public Railway URL in Dust.tt MCP configuration:

```
https://graphragmcp-production.up.railway.app/mcp
```

**Note:** The MCP client must send:
- `Content-Type: application/json`
- `Accept: application/json, text/event-stream`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GRAND_DEBAT_DATA_PATH` | Path to commune data | `./law_data` |
| `OPENAI_API_KEY` | OpenAI API key for queries | Required |
| `PORT` | HTTP server port | `8080` |

## Data Structure

Each commune folder should contain:

```
law_data/
├── Andilly/
│   ├── vdb_entities.json           # Entity embeddings
│   ├── kv_store_text_chunks.json   # Original contributions
│   ├── kv_store_community_reports.json  # Community summaries
│   └── graph_chunk_entity_relation.graphml  # Knowledge graph
├── Rochefort/
│   └── ...
└── ...
```

## Example Queries

```python
# List available communes
{"name": "grand_debat_list_communes", "arguments": {}}

# Query a commune
{
  "name": "grand_debat_query",
  "arguments": {
    "commune_id": "Rochefort",
    "query": "Quelles sont les principales préoccupations fiscales des citoyens?",
    "mode": "local"
  }
}

# Search for entities
{
  "name": "grand_debat_search_entities",
  "arguments": {
    "commune_id": "Andilly",
    "pattern": "impôt",
    "limit": 10
  }
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Dust.tt / LLM Client                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP / MCP Protocol
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Grand Débat MCP Server (Cloud Run)             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Tools:                                                │  │
│  │  - grand_debat_list_communes                         │  │
│  │  - grand_debat_query                                 │  │
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
└─────────────────────────────────────────────────────────────┘
```

## License

MIT
