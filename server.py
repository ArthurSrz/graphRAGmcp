#!/usr/bin/env python3
"""
Grand Débat National GraphRAG MCP Server

A remote MCP (Model Context Protocol) server that exposes GraphRAG capabilities
for the Grand Débat National "Cahiers de Doléances" dataset.

This server enables LLMs to:
- Query citizen contributions by commune using GraphRAG
- Search across entities and communities
- Retrieve provenance chains for transparency
- Explore the knowledge graph

Designed for deployment as a remote HTTP service (e.g., Cloud Run, Railway).
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Annotated
from enum import Enum

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field, ConfigDict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("grand-debat-mcp")

# Configure transport security for Railway deployment
# Disable DNS rebinding protection since Railway handles security at the edge
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

# Initialize the MCP server
mcp = FastMCP("grand_debat_mcp", transport_security=transport_security)

# Configuration
DATA_PATH = os.environ.get('GRAND_DEBAT_DATA_PATH', './law_data')


# ============================================================================
# Enums and Models
# ============================================================================

class QueryMode(str, Enum):
    """Query mode for GraphRAG."""
    LOCAL = "local"
    GLOBAL = "global"


class ResponseFormat(str, Enum):
    """Output format for responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class QueryInput(BaseModel):
    """Input for GraphRAG query."""
    model_config = ConfigDict(str_strip_whitespace=True)

    commune_id: str = Field(
        ...,
        description="Commune identifier (e.g., 'Andilly', 'Rochefort')",
        min_length=1
    )
    query: str = Field(
        ...,
        description="Question about citizen contributions in French",
        min_length=3
    )
    mode: QueryMode = Field(
        default=QueryMode.LOCAL,
        description="'local' for entity-based, 'global' for community summaries"
    )


class EntitySearchInput(BaseModel):
    """Input for entity search."""
    model_config = ConfigDict(str_strip_whitespace=True)

    commune_id: str = Field(..., description="Commune identifier")
    pattern: str = Field(
        ...,
        description="Search pattern (case-insensitive)",
        min_length=2
    )
    limit: int = Field(default=20, description="Max results", ge=1, le=100)


class CommuneInput(BaseModel):
    """Input for commune operations."""
    commune_id: str = Field(..., description="Commune identifier")
    limit: int = Field(default=10, description="Max items to return", ge=1, le=50)


# ============================================================================
# Helper Functions
# ============================================================================

def get_data_path() -> Path:
    """Get the base path for commune data."""
    return Path(DATA_PATH)


def list_communes() -> List[dict]:
    """List all available communes with statistics."""
    base_path = get_data_path()
    if not base_path.exists():
        return []

    communes = []
    for item in base_path.iterdir():
        if item.is_dir():
            has_entities = (item / "vdb_entities.json").exists()
            has_graph = (item / "graph_chunk_entity_relation.graphml").exists()
            has_chunks = (item / "kv_store_text_chunks.json").exists()
            has_communities = (item / "kv_store_community_reports.json").exists()

            if has_entities or has_graph:
                entity_count = 0
                community_count = 0
                contribution_count = 0

                try:
                    if has_entities:
                        with open(item / "vdb_entities.json", 'r') as f:
                            data = json.load(f)
                            if isinstance(data, dict) and 'data' in data:
                                entity_count = len(data['data'])
                            elif isinstance(data, dict) and '__data__' in data:
                                entity_count = len(data['__data__'])

                    if has_communities:
                        with open(item / "kv_store_community_reports.json", 'r') as f:
                            data = json.load(f)
                            community_count = len(data) if isinstance(data, dict) else 0

                    if has_chunks:
                        with open(item / "kv_store_text_chunks.json", 'r') as f:
                            data = json.load(f)
                            contribution_count = len(data) if isinstance(data, dict) else 0

                except Exception as e:
                    logger.warning(f"Error reading stats for {item.name}: {e}")

                communes.append({
                    'id': item.name,
                    'name': item.name.replace('_', ' '),
                    'entity_count': entity_count,
                    'community_count': community_count,
                    'contribution_count': contribution_count
                })

    return sorted(communes, key=lambda x: x['name'])


def get_commune_path(commune_id: str) -> Optional[Path]:
    """Get path to a commune's data directory."""
    base_path = get_data_path()
    commune_path = base_path / commune_id

    if commune_path.exists():
        return commune_path

    alt_path = base_path / commune_id.replace(' ', '_')
    if alt_path.exists():
        return alt_path

    return None


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool(
    name="grand_debat_list_communes",
    annotations={
        "title": "List Grand Débat Communes",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def grand_debat_list_communes() -> str:
    """
    List all available communes with their 'Cahiers de Doléances' data.

    Returns statistics about entities, communities, and contributions
    extracted from each commune's citizen participation records from
    the 2019 Grand Débat National.

    Returns:
        JSON with commune list and statistics
    """
    communes = list_communes()
    result = {
        "success": True,
        "total": len(communes),
        "communes": communes
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool(
    name="grand_debat_query",
    annotations={
        "title": "Query Grand Débat GraphRAG",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def grand_debat_query(
    commune_id: Annotated[str, Field(description="Commune identifier (e.g., 'Andilly', 'Rochefort')")],
    query: Annotated[str, Field(description="Question about citizen contributions in French", min_length=3)],
    mode: Annotated[QueryMode, Field(description="'local' for entity-based, 'global' for community summaries")] = QueryMode.LOCAL,
    include_sources: Annotated[bool, Field(description="Include exact citizen quotes and graph traversal path")] = True
) -> str:
    """
    Query a commune's 'Cahier de Doléances' using GraphRAG.

    Uses the nano_graphrag engine to answer questions about citizen
    contributions. Supports two modes:
    - 'local': Entity-based queries finding specific mentions and exact quotes
    - 'global': Community-based summaries for high-level themes

    When include_sources=True (default), returns the complete provenance chain:
    - Entities consulted (themes, actors, concepts)
    - Relationships traversed
    - Original citizen quotes (source_quotes) - exact text from contributions

    Args:
        commune_id: Commune identifier (e.g., 'Rochefort', 'Andilly')
        query: Question about citizen contributions in French
        mode: 'local' for entity-based, 'global' for community summaries
        include_sources: Include exact citizen quotes and provenance chain (default: True)

    Returns:
        JSON with answer and full provenance for end-to-end interpretability
    """
    commune_path = get_commune_path(commune_id)
    if not commune_path:
        available = [c['id'] for c in list_communes()[:10]]
        return json.dumps({
            "success": False,
            "error": f"Commune '{commune_id}' not found",
            "available_communes": available
        }, ensure_ascii=False)

    try:
        # Import GraphRAG
        import sys
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from nano_graphrag import GraphRAG, QueryParam
        from nano_graphrag._llm import gpt_4o_mini_complete

        rag = GraphRAG(
            working_dir=str(commune_path),
            best_model_func=gpt_4o_mini_complete,
            cheap_model_func=gpt_4o_mini_complete,
        )

        # Query with provenance for end-to-end interpretability
        result = await rag.aquery(
            query,
            param=QueryParam(mode=mode.value, return_provenance=include_sources)
        )

        # Handle response format based on provenance flag
        if include_sources and isinstance(result, dict):
            answer = result.get("answer", "")
            provenance = result.get("provenance", {})

            return json.dumps({
                "success": True,
                "commune_id": commune_id,
                "query": query,
                "mode": mode.value,
                "answer": answer,
                "provenance": {
                    "source_commune": commune_id,
                    "data_source": "Grand Débat National 2019",
                    "entities": provenance.get("entities", []),
                    "relationships": provenance.get("relationships", []),
                    "communities": provenance.get("communities", []),
                    "source_quotes": provenance.get("source_quotes", []),  # Exact citizen words
                    "analysis_points": provenance.get("analysis_points", []),
                }
            }, indent=2, ensure_ascii=False)
        else:
            # Fallback for string response (include_sources=False)
            return json.dumps({
                "success": True,
                "commune_id": commune_id,
                "query": query,
                "mode": mode.value,
                "answer": result if isinstance(result, str) else result.get("answer", ""),
                "provenance": {
                    "source_commune": commune_id,
                    "data_source": "Grand Débat National 2019"
                }
            }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Query error for {commune_id}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "commune_id": commune_id
        }, ensure_ascii=False)


@mcp.tool(
    name="grand_debat_query_all",
    annotations={
        "title": "Query All Communes",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def grand_debat_query_all(
    query: Annotated[str, Field(description="Question about citizen contributions in French", min_length=3)],
    mode: Annotated[QueryMode, Field(description="'local' for entity-based, 'global' for community summaries")] = QueryMode.GLOBAL,
    max_communes: Annotated[int, Field(description="Number of communes to query (default: 50 = ALL)", ge=1, le=50)] = 50,
    include_sources: Annotated[bool, Field(description="Include exact citizen quotes")] = True
) -> str:
    """
    Query across ALL 50 communes in a single call - no per-commune approval needed.

    This tool queries all communes with controlled concurrency to avoid API rate limits.
    Use this for broad questions like "What do French citizens think about X?"

    Args:
        query: Question about citizen contributions in French
        mode: 'global' recommended for cross-commune analysis (default)
        max_communes: How many communes to query (default: 50 = ALL)
        include_sources: Include exact citizen quotes (default: True)

    Returns:
        JSON with aggregated answers and provenance from all queried communes
    """
    import asyncio

    try:
        # Import GraphRAG
        import sys
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from nano_graphrag import GraphRAG, QueryParam
        from nano_graphrag._llm import gpt_4o_mini_complete

        # Get top communes by entity count
        all_communes = list_communes()
        if not all_communes:
            return json.dumps({
                "success": False,
                "error": "No communes found"
            }, ensure_ascii=False)

        # Sort by entity count and take top N
        sorted_communes = sorted(all_communes, key=lambda x: x.get('entity_count', 0), reverse=True)
        target_communes = sorted_communes[:max_communes]

        # Semaphore to limit concurrent API calls (avoid OpenAI rate limits)
        MAX_CONCURRENT = 5  # Max 5 concurrent OpenAI API calls
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def query_single_commune(commune_info):
            """Query a single commune with rate limiting."""
            async with semaphore:  # Acquire semaphore before making API call
                commune_id = commune_info['id']
                commune_path = get_commune_path(commune_id)
                if not commune_path:
                    return None

                try:
                    rag = GraphRAG(
                        working_dir=str(commune_path),
                        best_model_func=gpt_4o_mini_complete,
                        cheap_model_func=gpt_4o_mini_complete,
                    )

                    result = await rag.aquery(
                        query,
                        param=QueryParam(mode=mode.value, return_provenance=include_sources)
                    )

                    if isinstance(result, dict):
                        return {
                            "commune_id": commune_id,
                            "commune_name": commune_info.get('name', commune_id),
                            "entity_count": commune_info.get('entity_count', 0),
                            "answer": result.get("answer", ""),
                            "provenance": result.get("provenance", {})
                        }
                    else:
                        return {
                            "commune_id": commune_id,
                            "commune_name": commune_info.get('name', commune_id),
                            "entity_count": commune_info.get('entity_count', 0),
                            "answer": result,
                            "provenance": {}
                        }
                except Exception as e:
                    logger.warning(f"Query failed for {commune_id}: {e}")
                    return None

        # Query all communes with controlled concurrency
        logger.info(f"Querying {len(target_communes)} communes (max {MAX_CONCURRENT} concurrent)...")
        results = await asyncio.gather(*[query_single_commune(c) for c in target_communes])

        # Filter successful results
        successful_results = [r for r in results if r is not None]

        # Aggregate source quotes from all communes
        all_source_quotes = []
        all_entities = []
        all_communities = []

        for r in successful_results:
            prov = r.get("provenance", {})
            commune_id = r.get("commune_id", "")

            # Add commune attribution to each quote
            for quote in prov.get("source_quotes", []):
                all_source_quotes.append({
                    "commune": commune_id,
                    "content": quote.get("content", ""),
                    "chunk_id": quote.get("chunk_id", 0)
                })

            # Aggregate entities with commune attribution
            for entity in prov.get("entities", [])[:5]:  # Top 5 per commune
                all_entities.append({
                    "commune": commune_id,
                    **entity
                })

            # Aggregate communities
            for comm in prov.get("communities", [])[:3]:  # Top 3 per commune
                all_communities.append({
                    "commune": commune_id,
                    **comm
                })

        return json.dumps({
            "success": True,
            "query": query,
            "mode": mode.value,
            "communes_queried": len(successful_results),
            "communes_list": [r["commune_id"] for r in successful_results],
            "results": [
                {
                    "commune_id": r["commune_id"],
                    "commune_name": r["commune_name"],
                    "answer_summary": r["answer"][:500] + "..." if len(r["answer"]) > 500 else r["answer"]
                }
                for r in successful_results
            ],
            "aggregated_provenance": {
                "data_source": "Grand Débat National 2019",
                "total_source_quotes": len(all_source_quotes),
                "source_quotes": all_source_quotes[:30],  # Top 30 quotes across all communes
                "entities": all_entities[:50],  # Top 50 entities
                "communities": all_communities[:20],  # Top 20 communities
            }
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Query all error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool(
    name="grand_debat_search_entities",
    annotations={
        "title": "Search Entities",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def grand_debat_search_entities(
    commune_id: Annotated[str, Field(description="Commune identifier")],
    pattern: Annotated[str, Field(description="Search pattern (case-insensitive)", min_length=2)],
    limit: Annotated[int, Field(description="Max results", ge=1, le=100)] = 20
) -> str:
    """
    Search for entities matching a pattern in a commune's knowledge graph.

    Entities include themes, actors, concepts, and proposals extracted
    from citizen contributions.

    Args:
        commune_id: Commune identifier (e.g., 'Rochefort', 'Marans')
        pattern: Search pattern (case-insensitive)
        limit: Maximum number of results to return

    Returns:
        JSON with matching entities and descriptions
    """
    commune_path = get_commune_path(commune_id)
    if not commune_path:
        return json.dumps({
            "success": False,
            "error": f"Commune '{commune_id}' not found"
        }, ensure_ascii=False)

    try:
        entities_file = commune_path / "vdb_entities.json"
        if not entities_file.exists():
            return json.dumps({
                "success": False,
                "error": f"No entities for commune '{commune_id}'"
            }, ensure_ascii=False)

        with open(entities_file, 'r') as f:
            entities_data = json.load(f)

        all_entities = []
        if isinstance(entities_data, dict):
            if 'data' in entities_data and isinstance(entities_data['data'], list):
                for entity_info in entities_data['data']:
                    if isinstance(entity_info, dict):
                        all_entities.append({
                            'id': entity_info.get('__id__', ''),
                            'name': entity_info.get('entity_name', entity_info.get('__id__', '')),
                            'type': entity_info.get('entity_type', 'ENTITY'),
                            'description': (entity_info.get('description', '') or '')[:200]
                        })
            elif '__data__' in entities_data:
                for entity_id, entity_info in entities_data['__data__'].items():
                    if isinstance(entity_info, dict):
                        all_entities.append({
                            'id': entity_id,
                            'name': entity_info.get('entity_name', entity_id),
                            'type': entity_info.get('entity_type', 'UNKNOWN'),
                            'description': (entity_info.get('description', '') or '')[:200]
                        })

        pattern_lower = pattern.lower()
        matching = [
            e for e in all_entities
            if pattern_lower in e['name'].lower() or
               pattern_lower in e.get('description', '').lower()
        ][:limit]

        return json.dumps({
            "success": True,
            "commune_id": commune_id,
            "pattern": pattern,
            "matches": matching,
            "total_matches": len(matching),
            "total_entities": len(all_entities)
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Entity search error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool(
    name="grand_debat_get_communities",
    annotations={
        "title": "Get Community Reports",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def grand_debat_get_communities(
    commune_id: Annotated[str, Field(description="Commune identifier")],
    limit: Annotated[int, Field(description="Max items to return", ge=1, le=50)] = 10
) -> str:
    """
    Get community reports (thematic clusters) from a commune.

    Communities are groups of related entities and concepts identified
    by the Leiden clustering algorithm, representing major themes
    in citizen contributions.

    Args:
        commune_id: Commune identifier (e.g., 'Rivedoux_Plage')
        limit: Maximum number of communities to return

    Returns:
        JSON with community summaries and ratings
    """
    commune_path = get_commune_path(commune_id)
    if not commune_path:
        return json.dumps({
            "success": False,
            "error": f"Commune '{commune_id}' not found"
        }, ensure_ascii=False)

    try:
        communities_file = commune_path / "kv_store_community_reports.json"
        if not communities_file.exists():
            return json.dumps({
                "success": False,
                "error": f"No communities for commune '{commune_id}'"
            }, ensure_ascii=False)

        with open(communities_file, 'r') as f:
            communities_data = json.load(f)

        communities = []
        if isinstance(communities_data, dict):
            for comm_id, comm_info in list(communities_data.items())[:limit]:
                if isinstance(comm_info, dict):
                    communities.append({
                        'id': comm_id,
                        'title': comm_info.get('title', comm_id),
                        'summary': (comm_info.get('summary', '') or '')[:500],
                        'rating': comm_info.get('rating', 0),
                        'level': comm_info.get('level', 0)
                    })

        return json.dumps({
            "success": True,
            "commune_id": commune_id,
            "communities": communities,
            "total_communities": len(communities_data) if isinstance(communities_data, dict) else 0
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Communities error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool(
    name="grand_debat_get_contributions",
    annotations={
        "title": "Get Citizen Contributions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def grand_debat_get_contributions(
    commune_id: Annotated[str, Field(description="Commune identifier")],
    limit: Annotated[int, Field(description="Max items to return", ge=1, le=50)] = 10
) -> str:
    """
    Get sample citizen contributions from a commune.

    Returns original text excerpts from the 'Cahier de Doléances',
    representing citizens' opinions, proposals, and grievances.

    Args:
        commune_id: Commune identifier (e.g., 'Andilly')
        limit: Maximum number of contributions to return

    Returns:
        JSON with contribution previews
    """
    commune_path = get_commune_path(commune_id)
    if not commune_path:
        return json.dumps({
            "success": False,
            "error": f"Commune '{commune_id}' not found"
        }, ensure_ascii=False)

    try:
        chunks_file = commune_path / "kv_store_text_chunks.json"
        if not chunks_file.exists():
            return json.dumps({
                "success": False,
                "error": f"No contributions for commune '{commune_id}'"
            }, ensure_ascii=False)

        with open(chunks_file, 'r') as f:
            chunks_data = json.load(f)

        contributions = []
        if isinstance(chunks_data, dict):
            for chunk_id, chunk_info in list(chunks_data.items())[:limit]:
                if isinstance(chunk_info, dict):
                    content = chunk_info.get('content', '')
                    contributions.append({
                        'id': chunk_id,
                        'content_preview': content[:500] + ('...' if len(content) > 500 else ''),
                        'word_count': len(content.split()),
                        'order': chunk_info.get('chunk_order_index', 0)
                    })

        return json.dumps({
            "success": True,
            "commune_id": commune_id,
            "contributions": contributions,
            "total_contributions": len(chunks_data) if isinstance(chunks_data, dict) else 0
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Contributions error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Grand Débat MCP Server")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    parser.add_argument("--stdio", action="store_true", help="Use stdio transport")
    args = parser.parse_args()

    logger.info(f"Starting Grand Débat MCP Server...")
    logger.info(f"Data path: {DATA_PATH}")

    communes = list_communes()
    logger.info(f"Found {len(communes)} communes")

    if args.stdio:
        mcp.run()
    else:
        # For HTTP transport, use uvicorn to run the ASGI app
        import uvicorn
        uvicorn.run(
            mcp.streamable_http_app(),
            host=args.host,
            port=args.port,
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="*"
        )
