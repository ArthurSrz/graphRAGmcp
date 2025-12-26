#!/usr/bin/env python3
"""
Multi-Source GraphRAG MCP Server

A remote MCP (Model Context Protocol) server that exposes GraphRAG capabilities
for multiple data sources:
- Grand Débat National "Cahiers de Doléances" (civic data)
- Borges Library (literary analysis)
- Future data sources...

This server enables LLMs to:
- Query documents using GraphRAG across multiple corpora
- Search entities and communities
- Retrieve provenance chains for transparency
- Explore knowledge graphs

Designed for deployment as a remote HTTP service (e.g., Cloud Run, Railway).
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Annotated, Dict, Any
from enum import Enum

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field, ConfigDict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graphrag-mcp")

# Configure transport security for Railway deployment
# Disable DNS rebinding protection since Railway handles security at the edge
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

# Initialize the MCP server
mcp = FastMCP("graphrag_mcp", transport_security=transport_security)

# ============================================================================
# Multi-Source Configuration
# ============================================================================

# Data sources registry - each source has its own path and metadata
DATA_SOURCES: Dict[str, Dict[str, Any]] = {
    "grand_debat": {
        "path": os.environ.get('GRAND_DEBAT_DATA_PATH', './law_data'),
        "name": "Grand Débat National",
        "description": "Cahiers de Doléances 2019 - Citizen contributions from 50 communes in Charente-Maritime",
        "entity_label": "commune",  # What we call each collection (commune, book, etc.)
        "collection_label": "communes",
    },
    "borges_library": {
        "path": os.environ.get('BORGES_DATA_PATH', './book_data'),
        "name": "Borges Library",
        "description": "Literary analysis of French literature - entities, themes, and relationships",
        "entity_label": "book",
        "collection_label": "books",
    },
}

# Default data source
DEFAULT_DATA_SOURCE = os.environ.get('DEFAULT_DATA_SOURCE', 'grand_debat')

# Legacy compatibility - keep the old DATA_PATH for existing tools
DATA_PATH = DATA_SOURCES.get(DEFAULT_DATA_SOURCE, {}).get('path', './law_data')


# ============================================================================
# GraphRAG Instance Cache (Feature 006-graph-optimization, T015)
# ============================================================================

import time
from collections import OrderedDict

class GraphRAGCache:
    """
    LRU cache for GraphRAG instances to avoid re-initialization per query.

    Performance impact: GraphRAG init takes 15-30s per instance.
    With caching, subsequent queries to the same commune are instant.

    TTL: 5 minutes (300 seconds) to balance memory vs performance.
    Max size: 10 instances (covers typical multi-commune queries).
    """

    def __init__(self, maxsize: int = 10, ttl_seconds: int = 300):
        self._cache: OrderedDict = OrderedDict()  # path -> (instance, timestamp)
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, working_dir: str):
        """Get cached GraphRAG instance if valid, None otherwise."""
        if working_dir not in self._cache:
            self._misses += 1
            return None

        instance, timestamp = self._cache[working_dir]

        # Check TTL
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[working_dir]
            self._misses += 1
            logger.debug(f"GraphRAG cache expired for {working_dir}")
            return None

        # Move to end (LRU)
        self._cache.move_to_end(working_dir)
        self._hits += 1
        logger.debug(f"GraphRAG cache hit for {working_dir} (hits={self._hits}, misses={self._misses})")
        return instance

    def put(self, working_dir: str, instance):
        """Cache a GraphRAG instance."""
        # Evict oldest if at capacity
        while len(self._cache) >= self.maxsize:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"GraphRAG cache evicted: {oldest_key}")

        self._cache[working_dir] = (instance, time.time())
        logger.debug(f"GraphRAG cache stored: {working_dir} (size={len(self._cache)})")

    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "size": len(self._cache),
            "maxsize": self.maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0
        }

# Global cache instance
_graphrag_cache = GraphRAGCache(maxsize=10, ttl_seconds=300)


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

def get_data_source_config(source_id: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a data source."""
    return DATA_SOURCES.get(source_id)


def get_data_source_path(source_id: str) -> Optional[Path]:
    """Get the base path for a data source."""
    config = get_data_source_config(source_id)
    if config:
        path = Path(config['path'])
        if path.exists():
            return path
    return None


def list_data_sources_info() -> List[Dict[str, Any]]:
    """List all configured data sources with availability status."""
    sources = []
    for source_id, config in DATA_SOURCES.items():
        path = Path(config['path'])
        exists = path.exists()
        collection_count = 0
        if exists:
            collection_count = len([d for d in path.iterdir() if d.is_dir()])

        sources.append({
            "id": source_id,
            "name": config['name'],
            "description": config['description'],
            "available": exists,
            "collection_count": collection_count,
            "collection_label": config['collection_label'],
        })
    return sources


def get_data_path() -> Path:
    """Get the base path for commune data (legacy compatibility)."""
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
# MCP Tools - Generic Multi-Source
# ============================================================================

@mcp.tool(
    name="list_data_sources",
    annotations={
        "title": "List Available Data Sources",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def mcp_list_data_sources() -> str:
    """
    List all available data sources in this GraphRAG server.

    Each data source represents a corpus (e.g., Grand Débat National, Borges Library)
    with its own collections (communes, books, etc.).

    Returns:
        JSON with available data sources and their statistics
    """
    sources = list_data_sources_info()
    return json.dumps({
        "success": True,
        "data_sources": sources,
        "total": len(sources),
        "default_source": DEFAULT_DATA_SOURCE,
    }, indent=2, ensure_ascii=False)


@mcp.tool(
    name="list_collections",
    annotations={
        "title": "List Collections in Data Source",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def mcp_list_collections(
    data_source: Annotated[str, Field(description="Data source ID (e.g., 'grand_debat', 'borges_library')")] = DEFAULT_DATA_SOURCE
) -> str:
    """
    List all collections (communes, books, etc.) in a data source.

    Args:
        data_source: The data source to query (default: grand_debat)

    Returns:
        JSON with collections and their statistics
    """
    source_path = get_data_source_path(data_source)
    if not source_path:
        available = [s['id'] for s in list_data_sources_info() if s['available']]
        return json.dumps({
            "success": False,
            "error": f"Data source '{data_source}' not found or unavailable",
            "available_sources": available
        }, ensure_ascii=False)

    config = get_data_source_config(data_source)
    collections = []

    for item in source_path.iterdir():
        if item.is_dir():
            has_entities = (item / "vdb_entities.json").exists()
            has_graph = (item / "graph_chunk_entity_relation.graphml").exists()

            if has_entities or has_graph:
                entity_count = 0
                try:
                    if has_entities:
                        with open(item / "vdb_entities.json", 'r') as f:
                            data = json.load(f)
                            if isinstance(data, dict) and 'data' in data:
                                entity_count = len(data['data'])
                            elif isinstance(data, dict) and '__data__' in data:
                                entity_count = len(data['__data__'])
                except Exception:
                    pass

                collections.append({
                    'id': item.name,
                    'name': item.name.replace('_', ' '),
                    'entity_count': entity_count,
                })

    return json.dumps({
        "success": True,
        "data_source": data_source,
        "data_source_name": config['name'] if config else data_source,
        "collection_label": config['collection_label'] if config else "collections",
        "total": len(collections),
        "collections": sorted(collections, key=lambda x: x['name'])
    }, indent=2, ensure_ascii=False)


@mcp.tool(
    name="query",
    annotations={
        "title": "Query GraphRAG",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def mcp_query(
    query: Annotated[str, Field(description="Question to ask", min_length=3)],
    collection_id: Annotated[str, Field(description="Collection ID (commune, book, etc.)")],
    data_source: Annotated[str, Field(description="Data source ID")] = DEFAULT_DATA_SOURCE,
    mode: Annotated[QueryMode, Field(description="'local' for entity-based, 'global' for community summaries")] = QueryMode.LOCAL,
    include_sources: Annotated[bool, Field(description="Include source quotes and provenance")] = True
) -> str:
    """
    Query a collection using GraphRAG.

    Generic query tool that works with any data source (Grand Débat, Borges Library, etc.).

    Args:
        query: The question to ask
        collection_id: The collection to query (commune ID, book ID, etc.)
        data_source: The data source (default: grand_debat)
        mode: Query mode - 'local' for entities, 'global' for communities
        include_sources: Include provenance chain with source quotes

    Returns:
        JSON with answer and provenance for end-to-end interpretability
    """
    source_path = get_data_source_path(data_source)
    if not source_path:
        return json.dumps({
            "success": False,
            "error": f"Data source '{data_source}' not available"
        }, ensure_ascii=False)

    collection_path = source_path / collection_id
    if not collection_path.exists():
        # Try with underscores
        alt_path = source_path / collection_id.replace(' ', '_')
        if alt_path.exists():
            collection_path = alt_path
        else:
            return json.dumps({
                "success": False,
                "error": f"Collection '{collection_id}' not found in {data_source}"
            }, ensure_ascii=False)

    try:
        import sys
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from nano_graphrag import GraphRAG, QueryParam
        from nano_graphrag._llm import gpt_4o_mini_complete

        rag = GraphRAG(
            working_dir=str(collection_path),
            best_model_func=gpt_4o_mini_complete,
            cheap_model_func=gpt_4o_mini_complete,
        )

        result = await rag.aquery(
            query,
            param=QueryParam(mode=mode.value, return_provenance=include_sources)
        )

        config = get_data_source_config(data_source)

        if include_sources and isinstance(result, dict):
            answer = result.get("answer", "")
            provenance = result.get("provenance", {})

            return json.dumps({
                "success": True,
                "data_source": data_source,
                "data_source_name": config['name'] if config else data_source,
                "collection_id": collection_id,
                "query": query,
                "mode": mode.value,
                "answer": answer,
                "provenance": {
                    "source_collection": collection_id,
                    "data_source": config['name'] if config else data_source,
                    "entities": provenance.get("entities", []),
                    "relationships": provenance.get("relationships", []),
                    "communities": provenance.get("communities", []),
                    "source_quotes": provenance.get("source_quotes", []),
                }
            }, indent=2, ensure_ascii=False)
        else:
            return json.dumps({
                "success": True,
                "data_source": data_source,
                "collection_id": collection_id,
                "query": query,
                "mode": mode.value,
                "answer": result if isinstance(result, str) else result.get("answer", ""),
            }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Query error for {data_source}/{collection_id}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "data_source": data_source,
            "collection_id": collection_id
        }, ensure_ascii=False)


# ============================================================================
# MCP Tools - Grand Débat National (Legacy + Specific)
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
        # Feature 006-graph-optimization: Increased from 2 to 6 for better parallelism
        # With single_mode=True, this allows 6 concurrent API calls (was 4 with dual mode)
        MAX_CONCURRENT = 6  # Max 6 concurrent commune queries for improved throughput
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        # Feature 006-graph-optimization T016: Single mode option
        # When True, only runs global mode (halves LLM calls)
        # Global mode provides community summaries which are sufficient for cross-commune analysis
        single_mode = True  # Default to single mode for performance

        async def query_single_commune(commune_info):
            """
            Query a single commune with rate limiting.

            Feature 006-graph-optimization:
            - T015: Uses GraphRAG instance cache to avoid re-initialization
            - T016: single_mode=True skips local mode (50% fewer LLM calls)
            """
            async with semaphore:  # Acquire semaphore before making API call
                commune_id = commune_info['id']
                commune_path = get_commune_path(commune_id)
                if not commune_path:
                    return None

                try:
                    # T015: Try to get cached GraphRAG instance
                    working_dir = str(commune_path)
                    rag = _graphrag_cache.get(working_dir)

                    if rag is None:
                        # Cache miss - create new instance
                        rag = GraphRAG(
                            working_dir=working_dir,
                            best_model_func=gpt_4o_mini_complete,
                            cheap_model_func=gpt_4o_mini_complete,
                        )
                        _graphrag_cache.put(working_dir, rag)

                    # T016: Single mode optimization
                    local_result = None
                    merged_provenance = {}

                    if not single_mode:
                        # Original dual-mode: query both local and global
                        local_result = await rag.aquery(
                            query,
                            param=QueryParam(mode="local", return_provenance=include_sources)
                        )
                        await asyncio.sleep(0.5)  # Rate limit delay

                        if isinstance(local_result, dict):
                            local_prov = local_result.get("provenance", {}) or {}
                            merged_provenance.update({
                                "entities": local_prov.get("entities", []),
                                "relationships": local_prov.get("relationships", []),
                                "source_quotes": local_prov.get("source_quotes", []),
                            })

                    # Always run global mode
                    global_result = await rag.aquery(
                        query,
                        param=QueryParam(mode="global", return_provenance=include_sources)
                    )

                    if isinstance(global_result, dict):
                        global_prov = global_result.get("provenance", {}) or {}
                        merged_provenance["communities"] = global_prov.get("communities", [])

                    # Use global answer (better for cross-commune synthesis)
                    answer = ""
                    if isinstance(global_result, dict):
                        answer = global_result.get("answer", "")
                    elif isinstance(global_result, str):
                        answer = global_result

                    return {
                        "commune_id": commune_id,
                        "commune_name": commune_info.get('name', commune_id),
                        "entity_count": commune_info.get('entity_count', 0),
                        "answer": answer,
                        "provenance": merged_provenance
                    }
                except Exception as e:
                    logger.warning(f"Query failed for {commune_id}: {e}")
                    return None

        # Query all communes with controlled concurrency
        logger.info(f"Querying {len(target_communes)} communes (max {MAX_CONCURRENT} concurrent)...")
        results = await asyncio.gather(*[query_single_commune(c) for c in target_communes])

        # Filter successful results
        successful_results = [r for r in results if r is not None]

        # Aggregate provenance from all communes
        all_source_quotes = []
        all_entities = []
        all_relationships = []
        all_communities = []

        for r in successful_results:
            if r is None:
                continue
            prov = r.get("provenance", {}) or {}
            commune_id = r.get("commune_id", "")

            # Add commune attribution to each quote
            source_quotes = prov.get("source_quotes", []) or []
            for quote in source_quotes:
                if quote is None:
                    continue
                all_source_quotes.append({
                    "commune": commune_id,
                    "content": quote.get("content", "") if isinstance(quote, dict) else str(quote),
                    "chunk_id": quote.get("chunk_id", 0) if isinstance(quote, dict) else 0
                })

            # Aggregate entities with commune attribution
            entities = prov.get("entities", []) or []
            for entity in entities:  # All entities (removed limit)
                if entity is None:
                    continue
                if isinstance(entity, dict):
                    all_entities.append({
                        "source_commune": commune_id,
                        **entity
                    })

            # Aggregate relationships with commune attribution
            relationships = prov.get("relationships", []) or []
            for rel in relationships:  # All relationships
                if rel is None:
                    continue
                if isinstance(rel, dict):
                    all_relationships.append({
                        "source_commune": commune_id,
                        **rel
                    })

            # Aggregate communities
            communities = prov.get("communities", []) or []
            for comm in communities[:3]:  # Top 3 per commune
                if comm is None:
                    continue
                if isinstance(comm, dict):
                    all_communities.append({
                        "commune": commune_id,
                        **comm
                    })

        # Build results with null safety
        results_list = []
        communes_list = []
        for r in successful_results:
            if r is None or not isinstance(r, dict):
                continue
            commune_id = r.get("commune_id", "unknown")
            communes_list.append(commune_id)
            answer = r.get("answer", "") or ""
            results_list.append({
                "commune_id": commune_id,
                "commune_name": r.get("commune_name", commune_id),
                "answer_summary": answer[:500] + "..." if len(answer) > 500 else answer
            })

        return json.dumps({
            "success": True,
            "query": query,
            "mode": mode.value,
            "communes_queried": len(results_list),
            "communes_list": communes_list,
            "results": results_list,
            "aggregated_provenance": {
                "data_source": "Grand Débat National 2019",
                "total_source_quotes": len(all_source_quotes),
                "total_entities": len(all_entities),
                "total_relationships": len(all_relationships),
                "source_quotes": all_source_quotes[:30],  # Top 30 quotes across all communes
                "entities": all_entities,  # All entities from all communes
                "relationships": all_relationships,  # All relationships from all communes
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


@mcp.tool(
    name="grand_debat_get_full_graph",
    annotations={
        "title": "Get Full Entity Graph (No LLM)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def grand_debat_get_full_graph(
    max_communes: Annotated[int, Field(description="Max communes to load (default: 50 = ALL)", ge=1, le=50)] = 50,
    include_relationships: Annotated[bool, Field(description="Include relationships from GraphML files")] = True
) -> str:
    """
    Get the full entity graph from all communes WITHOUT running LLM queries.

    This tool directly reads entity data from vdb_entities.json files and
    optionally parses GraphML files for relationships. It's designed for
    fast initial graph loading (200+ nodes) without API calls or LLM costs.

    Perfect for:
    - Initial page load with full graph visualization
    - Exploring entity landscape before semantic queries
    - Performance-critical applications

    Args:
        max_communes: How many communes to load (default: 50 = ALL)
        include_relationships: Whether to parse GraphML for relationships (slower but complete)

    Returns:
        JSON with all entities and relationships across communes
    """
    try:
        # Get all communes sorted by entity count
        all_communes = list_communes()
        if not all_communes:
            return json.dumps({
                "success": False,
                "error": "No communes found"
            }, ensure_ascii=False)

        sorted_communes = sorted(all_communes, key=lambda x: x.get('entity_count', 0), reverse=True)
        target_communes = sorted_communes[:max_communes]

        all_entities = []
        all_relationships = []
        entity_id_to_commune = {}  # Track which commune each entity belongs to

        # Load entities from each commune
        for commune_info in target_communes:
            commune_id = commune_info['id']
            commune_path = get_commune_path(commune_id)
            if not commune_path:
                continue

            try:
                # Load entities from vdb_entities.json
                entities_file = commune_path / "vdb_entities.json"
                if entities_file.exists():
                    with open(entities_file, 'r') as f:
                        entities_data = json.load(f)

                    # Parse entity data (handles both formats)
                    if isinstance(entities_data, dict):
                        entity_list = []
                        if 'data' in entities_data and isinstance(entities_data['data'], list):
                            entity_list = entities_data['data']
                        elif '__data__' in entities_data:
                            entity_list = [
                                {"__id__": k, **v} if isinstance(v, dict) else {"__id__": k, "entity_name": str(v)}
                                for k, v in entities_data['__data__'].items()
                            ]

                        for entity_info in entity_list:
                            if not isinstance(entity_info, dict):
                                continue

                            entity_id = entity_info.get('__id__', '')
                            entity_name = entity_info.get('entity_name', entity_id)
                            # Remove quotes from entity names
                            if entity_name.startswith('"') and entity_name.endswith('"'):
                                entity_name = entity_name[1:-1]

                            all_entities.append({
                                "id": entity_id,
                                "name": entity_name,
                                "type": entity_info.get('entity_type', 'CIVIC_ENTITY'),
                                "description": entity_info.get('description', ''),
                                "source_commune": commune_id,
                                "importance_score": 0.5  # Default importance
                            })
                            entity_id_to_commune[entity_id] = commune_id

                # Load relationships from GraphML if requested
                if include_relationships:
                    graphml_file = commune_path / "graph_chunk_entity_relation.graphml"
                    if graphml_file.exists():
                        try:
                            import xml.etree.ElementTree as ET
                            tree = ET.parse(graphml_file)
                            root = tree.getroot()

                            # GraphML namespace
                            ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}

                            # Parse edges (relationships)
                            for edge in root.findall('.//g:edge', ns):
                                source_id = edge.get('source', '')
                                target_id = edge.get('target', '')

                                # Only include relationships between entities we loaded
                                if source_id in entity_id_to_commune and target_id in entity_id_to_commune:
                                    # Extract relationship type from edge data
                                    rel_type = "RELATED_TO"
                                    weight = 1.0
                                    description = ""

                                    for data in edge.findall('g:data', ns):
                                        key = data.get('key', '')
                                        if key == 'type' or key == 'relation':
                                            rel_type = data.text or "RELATED_TO"
                                        elif key == 'weight':
                                            try:
                                                weight = float(data.text or 1.0)
                                            except ValueError:
                                                weight = 1.0
                                        elif key == 'description':
                                            description = data.text or ""

                                    all_relationships.append({
                                        "source": source_id,
                                        "target": target_id,
                                        "type": rel_type,
                                        "weight": weight,
                                        "description": description,
                                        "source_commune": commune_id
                                    })

                        except Exception as e:
                            logger.warning(f"Failed to parse GraphML for {commune_id}: {e}")

            except Exception as e:
                logger.warning(f"Failed to load entities for {commune_id}: {e}")
                continue

        return json.dumps({
            "success": True,
            "total_communes": len(target_communes),
            "total_entities": len(all_entities),
            "total_relationships": len(all_relationships),
            "communes_loaded": [c['id'] for c in target_communes],
            "data_source": "Grand Débat National 2019",
            "provenance": {
                "entities": all_entities,
                "relationships": all_relationships,
                "source_quotes": [],  # No quotes in this fast-load mode
                "communities": []  # No communities in this fast-load mode
            }
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Get full graph error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Source GraphRAG MCP Server")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    parser.add_argument("--stdio", action="store_true", help="Use stdio transport")
    args = parser.parse_args()

    logger.info(f"Starting Multi-Source GraphRAG MCP Server...")
    logger.info(f"Default data source: {DEFAULT_DATA_SOURCE}")

    # Log all configured data sources
    for source_id, config in DATA_SOURCES.items():
        path = Path(config['path'])
        status = "AVAILABLE" if path.exists() else "NOT FOUND"
        collection_count = len([d for d in path.iterdir() if d.is_dir()]) if path.exists() else 0
        logger.info(f"  [{status}] {source_id}: {config['name']} ({collection_count} {config['collection_label']})")

    # Legacy: also log communes for backward compatibility
    communes = list_communes()
    logger.info(f"Grand Débat: {len(communes)} communes loaded")

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
