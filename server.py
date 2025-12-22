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
from typing import Optional, List
from enum import Enum

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("grand-debat-mcp")

# Initialize the MCP server
mcp = FastMCP("grand_debat_mcp")

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
async def grand_debat_query(params: QueryInput) -> str:
    """
    Query a commune's 'Cahier de Doléances' using GraphRAG.

    Uses the nano_graphrag engine to answer questions about citizen
    contributions. Supports two modes:
    - 'local': Entity-based queries finding specific mentions
    - 'global': Community-based summaries for high-level themes

    Args:
        params: Query parameters including commune_id, query text, and mode

    Returns:
        JSON with answer and provenance information
    """
    commune_path = get_commune_path(params.commune_id)
    if not commune_path:
        available = [c['id'] for c in list_communes()[:10]]
        return json.dumps({
            "success": False,
            "error": f"Commune '{params.commune_id}' not found",
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

        result = await rag.aquery(
            params.query,
            param=QueryParam(mode=params.mode.value)
        )

        return json.dumps({
            "success": True,
            "commune_id": params.commune_id,
            "query": params.query,
            "mode": params.mode.value,
            "answer": result,
            "provenance": {
                "source_commune": params.commune_id,
                "data_source": "Grand Débat National 2019"
            }
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Query error for {params.commune_id}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "commune_id": params.commune_id
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
async def grand_debat_search_entities(params: EntitySearchInput) -> str:
    """
    Search for entities matching a pattern in a commune's knowledge graph.

    Entities include themes, actors, concepts, and proposals extracted
    from citizen contributions.

    Args:
        params: Search parameters including commune_id, pattern, and limit

    Returns:
        JSON with matching entities and descriptions
    """
    commune_path = get_commune_path(params.commune_id)
    if not commune_path:
        return json.dumps({
            "success": False,
            "error": f"Commune '{params.commune_id}' not found"
        }, ensure_ascii=False)

    try:
        entities_file = commune_path / "vdb_entities.json"
        if not entities_file.exists():
            return json.dumps({
                "success": False,
                "error": f"No entities for commune '{params.commune_id}'"
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

        pattern_lower = params.pattern.lower()
        matching = [
            e for e in all_entities
            if pattern_lower in e['name'].lower() or
               pattern_lower in e.get('description', '').lower()
        ][:params.limit]

        return json.dumps({
            "success": True,
            "commune_id": params.commune_id,
            "pattern": params.pattern,
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
async def grand_debat_get_communities(params: CommuneInput) -> str:
    """
    Get community reports (thematic clusters) from a commune.

    Communities are groups of related entities and concepts identified
    by the Leiden clustering algorithm, representing major themes
    in citizen contributions.

    Args:
        params: Commune ID and limit

    Returns:
        JSON with community summaries and ratings
    """
    commune_path = get_commune_path(params.commune_id)
    if not commune_path:
        return json.dumps({
            "success": False,
            "error": f"Commune '{params.commune_id}' not found"
        }, ensure_ascii=False)

    try:
        communities_file = commune_path / "kv_store_community_reports.json"
        if not communities_file.exists():
            return json.dumps({
                "success": False,
                "error": f"No communities for commune '{params.commune_id}'"
            }, ensure_ascii=False)

        with open(communities_file, 'r') as f:
            communities_data = json.load(f)

        communities = []
        if isinstance(communities_data, dict):
            for comm_id, comm_info in list(communities_data.items())[:params.limit]:
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
            "commune_id": params.commune_id,
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
async def grand_debat_get_contributions(params: CommuneInput) -> str:
    """
    Get sample citizen contributions from a commune.

    Returns original text excerpts from the 'Cahier de Doléances',
    representing citizens' opinions, proposals, and grievances.

    Args:
        params: Commune ID and limit

    Returns:
        JSON with contribution previews
    """
    commune_path = get_commune_path(params.commune_id)
    if not commune_path:
        return json.dumps({
            "success": False,
            "error": f"Commune '{params.commune_id}' not found"
        }, ensure_ascii=False)

    try:
        chunks_file = commune_path / "kv_store_text_chunks.json"
        if not chunks_file.exists():
            return json.dumps({
                "success": False,
                "error": f"No contributions for commune '{params.commune_id}'"
            }, ensure_ascii=False)

        with open(chunks_file, 'r') as f:
            chunks_data = json.load(f)

        contributions = []
        if isinstance(chunks_data, dict):
            for chunk_id, chunk_info in list(chunks_data.items())[:params.limit]:
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
            "commune_id": params.commune_id,
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
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
