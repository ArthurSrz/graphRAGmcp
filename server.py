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
import asyncio
from pathlib import Path
from typing import Optional, List, Annotated, Dict, Any, Set, Tuple
from enum import Enum

from mcp.server.fastmcp import FastMCP

# Feature 007-mcp-graph-optimization: Pre-computed graph index
from graph_index import GraphIndex, get_graph_index, get_cached_graph_index
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
from collections import OrderedDict, defaultdict

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
# PERFORMANCE FIX: Increased from maxsize=10 to cover all 50 communes
# Increased TTL from 5min to 15min to reduce re-initialization during analysis
_graphrag_cache = GraphRAGCache(maxsize=50, ttl_seconds=900)


# ============================================================================
# GraphIndex Pre-loading (Feature 007-mcp-graph-optimization, T001/T002)
# ============================================================================

# Global GraphIndex singleton - initialized lazily on first use
_graph_index: Optional[GraphIndex] = None
_graph_index_init_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None


async def ensure_graph_index_initialized() -> GraphIndex:
    """
    Ensure GraphIndex is initialized. Lazy loading on first query.

    Thread-safe via asyncio lock. Called automatically by expand_via_index().
    """
    global _graph_index

    if _graph_index is not None:
        return _graph_index

    # Use lock for thread-safe initialization
    async with asyncio.Lock():
        if _graph_index is not None:
            return _graph_index

        logger.info("Initializing GraphIndex for all communes...")
        _graph_index = GraphIndex(DATA_PATH)
        await _graph_index.initialize()
        logger.info(f"GraphIndex ready: {_graph_index.stats}")

    return _graph_index


# ============================================================================
# CommunityCache Pre-loading (Feature 007-mcp-graph-optimization, T003/T004)
# ============================================================================

class CommunityCache:
    """
    Pre-loaded cache of community reports for O(1) keyword search.

    Feature 007-mcp-graph-optimization T003: Eliminates 50 file opens per query.

    Performance impact: 8-12s -> <100ms for community selection.

    Structure:
        _communities: Dict[commune_id, Dict[community_id, CommunityReport]]
        _keyword_index: Dict[keyword, List[(commune_id, community_id, score)]]
    """

    def __init__(self, data_path: str, ttl_seconds: int = 300):
        self.data_path = Path(data_path)
        self.ttl_seconds = ttl_seconds
        self._communities: Dict[str, Dict[str, dict]] = {}
        self._keyword_index: Dict[str, List[tuple]] = defaultdict(list)
        self._last_refresh = 0.0
        self._load_time_ms = 0

    async def initialize(self) -> None:
        """Load all community reports into memory."""
        await self._refresh_cache()

    async def _refresh_cache(self) -> None:
        """Refresh cache from disk (async-safe)."""
        import re
        start_time = time.time()

        # French stop words for keyword extraction
        stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou',
                      'que', 'qui', 'dans', 'pour', 'sur', 'avec', 'par', 'est', 'sont',
                      'ce', 'cette', 'ces', 'au', 'aux', 'en', 'il', 'elle', 'nous', 'vous'}

        self._communities.clear()
        self._keyword_index.clear()

        # Discover communes
        communes = []
        for item in self.data_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                communities_file = item / "kv_store_community_reports.json"
                if communities_file.exists():
                    communes.append((item.name, communities_file))

        # Load all community reports
        for commune_id, communities_file in communes:
            try:
                with open(communities_file, 'r') as f:
                    data = json.load(f)

                self._communities[commune_id] = {}

                for comm_id, comm_data in data.items():
                    report = comm_data.get('report_json', {})
                    if not report:
                        continue

                    rating = report.get('rating', 0)
                    if rating < 4.0:  # Skip low-quality communities
                        continue

                    title = report.get('title', '')
                    summary = report.get('summary', '')

                    # Store community data
                    self._communities[commune_id][comm_id] = {
                        'commune_id': commune_id,
                        'community_id': comm_id,
                        'title': title,
                        'summary': summary,
                        'rating': rating,
                        'nodes': comm_data.get('nodes', []),
                        'chunk_ids': comm_data.get('chunk_ids', []),
                    }

                    # Build keyword index
                    text = f"{title} {summary}".lower()
                    keywords = set(re.findall(r'\b\w{3,}\b', text)) - stop_words

                    for keyword in keywords:
                        # Title match = 3x weight, summary match = 1x weight
                        title_score = 3 if keyword in title.lower() else 0
                        summary_score = 1 if keyword in summary.lower() else 0
                        total_score = title_score + summary_score
                        if total_score > 0:
                            self._keyword_index[keyword].append((
                                commune_id, comm_id, total_score
                            ))

            except Exception as e:
                logger.warning(f"Failed to load communities for {commune_id}: {e}")
                continue

        self._last_refresh = time.time()
        self._load_time_ms = int((time.time() - start_time) * 1000)

        total_communities = sum(len(c) for c in self._communities.values())
        logger.info(
            f"CommunityCache loaded: {total_communities} communities, "
            f"{len(self._keyword_index)} keywords, "
            f"{len(self._communities)} communes in {self._load_time_ms}ms"
        )

    def search(self, query: str, max_results: int = 15, max_communes: int = 50) -> List[dict]:
        """
        Search communities by keyword match.

        Feature 007-mcp-graph-optimization T004: O(keywords) lookup vs O(50 files).

        Args:
            query: Search query
            max_results: Maximum communities to return
            max_communes: Maximum communes to search

        Returns:
            List of matching community dicts sorted by relevance
        """
        import re
        stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou',
                      'que', 'qui', 'dans', 'pour', 'sur', 'avec', 'par', 'est', 'sont',
                      'ce', 'cette', 'ces', 'au', 'aux', 'en', 'il', 'elle', 'nous', 'vous'}

        query_words = set(re.findall(r'\b\w{3,}\b', query.lower())) - stop_words

        if not query_words:
            return []

        # Aggregate scores per (commune_id, community_id)
        scores: Dict[tuple, float] = defaultdict(float)

        for keyword in query_words:
            for commune_id, comm_id, base_score in self._keyword_index.get(keyword, []):
                scores[(commune_id, comm_id)] += base_score

        # Build result list with full community data
        results = []
        seen_communes = set()

        # Sort by score descending
        sorted_matches = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        for (commune_id, comm_id), score in sorted_matches:
            if len(results) >= max_results:
                break

            if commune_id in seen_communes and len(seen_communes) >= max_communes:
                continue

            community = self._communities.get(commune_id, {}).get(comm_id)
            if community:
                community_copy = community.copy()
                community_copy['score'] = score
                results.append(community_copy)
                seen_communes.add(commune_id)

        return results

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            'total_communities': sum(len(c) for c in self._communities.values()),
            'total_communes': len(self._communities),
            'total_keywords': len(self._keyword_index),
            'load_time_ms': self._load_time_ms,
            'last_refresh': self._last_refresh
        }


# Global CommunityCache singleton
_community_cache: Optional[CommunityCache] = None


async def ensure_community_cache_initialized() -> CommunityCache:
    """
    Ensure CommunityCache is initialized. Lazy loading on first use.
    """
    global _community_cache

    if _community_cache is not None:
        return _community_cache

    async with asyncio.Lock():
        if _community_cache is not None:
            return _community_cache

        logger.info("Initializing CommunityCache for all communes...")
        _community_cache = CommunityCache(DATA_PATH)
        await _community_cache.initialize()
        logger.info(f"CommunityCache ready: {_community_cache.stats}")

    return _community_cache


# ============================================================================
# Parallel Chunk Loading (Feature 007-mcp-graph-optimization T007)
# ============================================================================

async def load_chunks_parallel(
    chunk_requests: List[Tuple[str, str]],  # [(chunk_id, source_commune), ...]
    max_chunks_per_commune: int = 50
) -> List[dict]:
    """
    Load text chunks in parallel, grouped by commune.

    Optimizations:
    - Group chunk IDs by commune to open each file only once
    - Use asyncio.gather() for parallel file I/O
    - Return immediately for communes with no chunks

    Args:
        chunk_requests: List of (chunk_id, source_commune) tuples
        max_chunks_per_commune: Max chunks to extract per commune file

    Returns:
        List of chunk dicts with id, content, commune
    """
    # Group by commune to minimize file I/O
    chunks_by_commune: Dict[str, List[str]] = defaultdict(list)
    for chunk_id, commune in chunk_requests:
        if commune:
            chunks_by_commune[commune].append(chunk_id)

    async def load_commune_chunks(commune_id: str, chunk_ids: List[str]) -> List[dict]:
        """Load chunks for a single commune asynchronously."""
        result = []
        commune_path = get_commune_path(commune_id)
        if not commune_path:
            return result

        chunks_file = commune_path / "kv_store_text_chunks.json"
        if not chunks_file.exists():
            return result

        try:
            # Use asyncio.to_thread for non-blocking file I/O
            def read_file():
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    return json.load(f)

            text_chunks = await asyncio.to_thread(read_file)

            # Extract requested chunks
            for chunk_id in chunk_ids[:max_chunks_per_commune]:
                if chunk_id in text_chunks:
                    chunk_data = text_chunks[chunk_id]
                    result.append({
                        "id": chunk_id,
                        "content": chunk_data.get("content", "")[:500],
                        "commune": commune_id
                    })

        except Exception as e:
            logger.warning(f"Error loading chunks for {commune_id}: {e}")

        return result

    # Launch all commune loads in parallel
    tasks = [
        load_commune_chunks(commune, chunk_ids)
        for commune, chunk_ids in chunks_by_commune.items()
    ]

    if not tasks:
        return []

    # Gather results from all communes
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten and filter exceptions
    all_chunks = []
    for result in results:
        if isinstance(result, list):
            all_chunks.extend(result)
        elif isinstance(result, Exception):
            logger.warning(f"Chunk loading failed: {result}")

    return all_chunks


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
# Optimized Query Helpers (Feature: Single LLM Call Architecture)
# ============================================================================

def load_community_reports(commune_id: str) -> list:
    """Load pre-computed community reports (no LLM call needed).

    Community reports are generated during indexing and stored as JSON.
    This provides instant access to thematic summaries.
    """
    commune_path = get_commune_path(commune_id)
    if not commune_path:
        return []

    communities_file = commune_path / "kv_store_community_reports.json"
    if not communities_file.exists():
        return []

    try:
        with open(communities_file, 'r') as f:
            data = json.load(f)

        return [
            {
                "commune": commune_id,
                "title": c.get("title", ""),
                "summary": (c.get("summary", "") or "")[:400],
                "rating": c.get("rating", 0)
            }
            for c in list(data.values())[:5]  # Top 5 per commune
        ]
    except Exception as e:
        logger.warning(f"Failed to load communities for {commune_id}: {e}")
        return []


def build_context_from_graph(entities: list, communities: list, query: str, max_context_chars: int = 12000) -> str:
    """Build LLM context from aggregated graph data.

    Uses simple keyword matching to find relevant entities,
    then combines with community summaries for rich context.

    Args:
        entities: All entities from GraphML files
        communities: All community reports from JSON
        query: User's question
        max_context_chars: Maximum context size (default 12k for gpt-5-nano)

    Returns:
        Formatted context string for LLM prompt
    """
    import re

    # Extract keywords from query (French-aware)
    query_lower = query.lower()
    # Remove common French stop words
    stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'que', 'qui', 'dans', 'pour', 'sur', 'avec', 'par', 'est', 'sont', 'ce', 'cette', 'ces'}
    query_words = set(re.findall(r'\b\w{3,}\b', query_lower)) - stop_words

    # Score entities by relevance
    def score_entity(e):
        score = 0
        name = (e.get('name', '') or '').lower()
        desc = (e.get('description', '') or '').lower()
        for word in query_words:
            if word in name:
                score += 3
            if word in desc:
                score += 1
        return score

    # Get top relevant entities
    scored_entities = [(e, score_entity(e)) for e in entities]
    relevant_entities = sorted([e for e, s in scored_entities if s > 0],
                               key=lambda x: score_entity(x), reverse=True)[:40]

    # If no keyword matches, take entities with descriptions (no limit)
    if not relevant_entities:
        relevant_entities = [e for e in entities if e.get('description')]

    context_parts = []
    current_size = 0

    # Add relevant entities
    if relevant_entities:
        context_parts.append("## Entités pertinentes du graphe\n")
        for e in relevant_entities:
            name = e.get('name', 'Unknown')
            commune = e.get('source_commune', '')
            desc = (e.get('description', '') or '')[:250]
            line = f"- **{name}** ({commune}): {desc}\n"
            if current_size + len(line) > max_context_chars * 0.6:
                break
            context_parts.append(line)
            current_size += len(line)

    # Add community summaries (pre-computed thematic clusters)
    if communities:
        context_parts.append("\n## Synthèses thématiques par commune\n")
        # Sort by rating (importance)
        sorted_communities = sorted(communities, key=lambda x: x.get('rating', 0), reverse=True)
        for c in sorted_communities[:25]:
            commune = c.get('commune', '')
            title = c.get('title', '')
            summary = c.get('summary', '')[:300]
            line = f"- [{commune}] **{title}**: {summary}\n"
            if current_size + len(line) > max_context_chars:
                break
            context_parts.append(line)
            current_size += len(line)

    return "".join(context_parts)


# ============================================================================
# Community-First Retrieval Helpers (Latency Optimization)
# ============================================================================

async def select_communities_by_keywords(query: str, max_communes: int = 50) -> list:
    """
    Select relevant communities via keyword matching using CommunityCache.

    Feature 007-mcp-graph-optimization T004: Uses pre-loaded cache instead of file I/O.

    Performance improvement: 8-12s -> <100ms (100x faster).

    Args:
        query: Search query in French
        max_communes: Maximum communes to search (default 50)

    Returns:
        List of matching community dicts sorted by relevance
    """
    # Ensure cache is initialized (lazy load on first use)
    cache = await ensure_community_cache_initialized()

    # Use cached keyword search
    communities = cache.search(query, max_results=15, max_communes=max_communes)

    logger.debug(
        f"select_communities_by_keywords: '{query[:50]}...' -> "
        f"{len(communities)} communities (cached)"
    )

    return communities


def extract_entities_from_communities(communities: list) -> list:
    """
    Extract entity IDs directly from community nodes.

    No vector DB search needed - communities already contain entity references.
    Expected latency: <10ms (pure Python set operations)
    """
    entity_set = set()
    for comm in communities:
        for node_id in comm.get('nodes', []):
            # Clean up quoted format: '"ENTITY_NAME"' -> 'ENTITY_NAME'
            clean_id = str(node_id).strip().strip('"')
            if clean_id:
                entity_set.add(clean_id)
    return list(entity_set)[:100]


def expand_via_graphml(seed_entities: list, commune_ids: set, max_hops: int = 2) -> tuple:
    """
    BFS expansion through GraphML relationships.

    Discovers multi-hop connections from seed entities.
    Expected latency: 500ms-2s (GraphML parsing + in-memory BFS)

    Returns:
        (entities, paths) - expanded entities with metadata, relationship paths
    """
    from collections import defaultdict, deque
    import xml.etree.ElementTree as ET

    adjacency = defaultdict(list)
    entity_data = {}

    # Parse GraphML files for relevant communes only
    for cid in commune_ids:
        commune_path = get_commune_path(cid)
        if not commune_path:
            continue
        graphml = commune_path / "graph_chunk_entity_relation.graphml"
        if not graphml.exists():
            continue

        try:
            tree = ET.parse(graphml)
            root = tree.getroot()
            ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}

            # Build key map for data extraction
            key_map = {}
            for k in root.findall('g:key', ns):
                key_map[k.get('id', '')] = k.get('attr.name', '')

            def get_data(elem, name):
                for d in elem.findall('g:data', ns):
                    if key_map.get(d.get('key', '')) == name:
                        return (d.text or '').strip().strip('"')
                return ''

            # Parse nodes
            for node in root.findall('.//g:node', ns):
                nid = node.get('id', '').strip('"')
                if nid:
                    entity_data[nid] = {
                        'name': get_data(node, 'entity_name') or nid,
                        'type': get_data(node, 'entity_type'),
                        'description': get_data(node, 'description')[:300],
                        'commune': cid
                    }

            # Parse edges into adjacency list
            for edge in root.findall('.//g:edge', ns):
                src = edge.get('source', '').strip('"')
                tgt = edge.get('target', '').strip('"')
                # Try multiple field names for relationship type (GraphML uses 'type' via attr.name)
                rel = get_data(edge, 'type') or get_data(edge, 'relationship_type') or get_data(edge, 'label') or 'RELATED_TO'
                if src and tgt:
                    adjacency[src].append((tgt, rel))
                    adjacency[tgt].append((src, rel))
        except Exception as e:
            logger.warning(f"Failed to parse GraphML for {cid}: {e}")
            continue

    # BFS from seed entities
    visited = set()
    queue = deque()
    paths = []

    # Initialize with seeds that exist in our graph
    for e in seed_entities:
        if e in entity_data or e in adjacency:
            visited.add(e)
            queue.append((e, 0))

    while queue and len(visited) < 200:
        entity, depth = queue.popleft()
        if depth >= max_hops:
            continue

        for neighbor, rel in adjacency.get(entity, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
                paths.append({
                    'source': entity,
                    'target': neighbor,
                    'type': rel,
                    'hop': depth + 1
                })

    # Build entity list with metadata
    entities = []
    for e in visited:
        if e in entity_data:
            entities.append({**entity_data[e], 'id': e})

    return entities, paths  # No limit - return full subgraph


async def expand_via_index(
    seed_entities: list,
    commune_ids: set,
    max_hops: int = 2,
    max_results: int = 200
) -> tuple:
    """
    Multi-hop expansion using pre-loaded GraphIndex.

    Feature 007-mcp-graph-optimization T002: Replaces expand_via_graphml().

    Performance: O(1) neighbor lookups vs O(n) XML parsing.
    Expected latency: <50ms (vs 25-30s for GraphML parsing).

    Uses weighted Dijkstra traversal (T005) with entity type prioritization (T006).

    Args:
        seed_entities: Starting entity IDs for expansion
        commune_ids: Set of commune IDs to filter results (or None for all)
        max_hops: Maximum traversal depth (default 2)
        max_results: Maximum entities to return (default 200)

    Returns:
        (entities, paths) - Entity metadata dicts and traversal paths
    """
    # Ensure GraphIndex is initialized
    index = await ensure_graph_index_initialized()

    # Use the weighted expansion from GraphIndex
    commune_filter = set(commune_ids) if commune_ids else None

    entities, paths = index.expand_weighted(
        seed_entities=seed_entities,
        max_hops=max_hops,
        max_results=max_results,
        commune_filter=commune_filter
    )

    logger.debug(
        f"expand_via_index: {len(seed_entities)} seeds -> "
        f"{len(entities)} entities, {len(paths)} paths "
        f"(filtered to {len(commune_ids) if commune_ids else 'all'} communes)"
    )

    return entities, paths


async def search_entities_globally(query: str, max_results: int = 100) -> List[dict]:
    """
    Search entities by keywords across ALL communes using GraphIndex.

    Feature: Fix for 9-commune limitation - ensures corpus-wide search.

    This function searches entity names and descriptions across all 55 communes,
    not just communities that match the query keywords.

    Performance: O(n) scan but very fast (<100ms for 21K entities)
    since GraphIndex is pre-loaded in memory.

    Args:
        query: Search query in French
        max_results: Maximum entities to return (default 100)

    Returns:
        List of matching entity dicts with scores
    """
    import re

    # Ensure GraphIndex is initialized
    index = await ensure_graph_index_initialized()

    # French stop words
    stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou',
                  'que', 'qui', 'dans', 'pour', 'sur', 'avec', 'par', 'est', 'sont',
                  'ce', 'cette', 'ces', 'au', 'aux', 'en', 'il', 'elle', 'nous', 'vous',
                  'tous', 'tout', 'plus', 'moins', 'entre', 'comme', 'être', 'avoir'}

    # Extract query keywords
    query_words = set(re.findall(r'\b\w{3,}\b', query.lower())) - stop_words

    if not query_words:
        return []

    # Score each entity by keyword matches
    scored_entities = []

    for entity_id, metadata in index._entities.items():
        # Search in entity name and description
        name_lower = metadata.name.lower()
        desc_lower = metadata.description.lower()

        score = 0
        for keyword in query_words:
            # Name match = 5 points (very relevant)
            if keyword in name_lower:
                score += 5
            # Description match = 1 point
            if keyword in desc_lower:
                score += 1

        if score > 0:
            scored_entities.append({
                'id': entity_id,
                'name': metadata.name,
                'type': metadata.entity_type,
                'description': metadata.description,
                'commune': metadata.commune,
                'score': score
            })

    # Sort by score descending
    scored_entities.sort(key=lambda x: x['score'], reverse=True)

    # Return top results
    results = scored_entities[:max_results]

    logger.debug(
        f"search_entities_globally: '{query[:50]}...' -> "
        f"{len(results)} entities from {len(set(e['commune'] for e in results))} communes"
    )

    return results


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
        from nano_graphrag._llm import gpt_5_nano_complete

        rag = GraphRAG(
            working_dir=str(collection_path),
            best_model_func=gpt_5_nano_complete,
            cheap_model_func=gpt_5_nano_complete,
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
                    # Constitution Principle V: End-to-End Interpretability
                    # Each source_quote must include collection attribution for provenance chain
                    "source_quotes": [
                        {**quote, "commune": collection_id}
                        for quote in provenance.get("source_quotes", [])
                    ],
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
        from nano_graphrag._llm import gpt_5_nano_complete

        # Use cached GraphRAG instance to avoid slow NanoVectorDB re-initialization
        working_dir = str(commune_path)
        rag = _graphrag_cache.get(working_dir)
        if rag is None:
            rag = GraphRAG(
                working_dir=working_dir,
                best_model_func=gpt_5_nano_complete,
                cheap_model_func=gpt_5_nano_complete,
            )
            _graphrag_cache.put(working_dir, rag)

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
                    "data_source": "Grand Debat National 2019",
                    "entities": provenance.get("entities", []),
                    "relationships": provenance.get("relationships", []),
                    "communities": provenance.get("communities", []),
                    # Constitution Principle V: End-to-End Interpretability
                    # Each source_quote must include commune attribution for provenance chain
                    "source_quotes": [
                        {**quote, "commune": commune_id}
                        for quote in provenance.get("source_quotes", [])
                    ],
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
        "title": "Query All Communes (Optimized)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def grand_debat_query_all(
    query: Annotated[str, Field(description="Question about citizen contributions in French", min_length=3)],
    mode: Annotated[QueryMode, Field(description="'local' for entity-based, 'global' for community summaries")] = QueryMode.GLOBAL,
    max_communes: Annotated[int, Field(description="Number of communes to include (default: 50 = ALL)", ge=1, le=50)] = 50,
    include_sources: Annotated[bool, Field(description="Include provenance chain")] = True
) -> str:
    """
    Query across ALL 50 communes with ONE aggregated LLM call.

    OPTIMIZED ARCHITECTURE:
    1. Parallel GraphML loading (fast file I/O, no LLM)
    2. Parallel community report loading (pre-computed JSON)
    3. Context aggregation with relevance scoring
    4. ONE LLM call with combined context

    Performance: ~5-10 seconds (vs 25+ minutes with old per-commune approach)

    Args:
        query: Question about citizen contributions in French
        mode: 'global' for community summaries, 'local' for entity-based (default: global)
        max_communes: How many communes to include (default: 50 = ALL)
        include_sources: Include provenance chain (default: True)

    Returns:
        JSON with synthesized answer and aggregated provenance from all communes
    """
    import asyncio
    import xml.etree.ElementTree as ET
    from concurrent.futures import ThreadPoolExecutor

    try:
        # Import LLM function
        import sys
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from nano_graphrag._llm import gpt_5_nano_complete

        # Get all communes
        all_communes = list_communes()
        if not all_communes:
            return json.dumps({
                "success": False,
                "error": "No communes found"
            }, ensure_ascii=False)

        # Sort by entity count and take top N
        sorted_communes = sorted(all_communes, key=lambda x: x.get('entity_count', 0), reverse=True)
        target_communes = sorted_communes[:max_communes]

        logger.info(f"Optimized query_all: Loading {len(target_communes)} communes...")

        # ============================================================
        # STEP 1: Parallel GraphML loading (reuse get_full_graph code)
        # ============================================================
        def parse_graphml_for_query(commune_info: dict) -> tuple:
            """Parse GraphML file - runs in thread pool."""
            commune_id = commune_info['id']
            commune_path = get_commune_path(commune_id)
            if not commune_path:
                return [], commune_id

            graphml_file = commune_path / "graph_chunk_entity_relation.graphml"
            if not graphml_file.exists():
                return [], commune_id

            entities = []
            try:
                tree = ET.parse(graphml_file)
                root = tree.getroot()
                ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}

                # Build key mapping
                key_map = {}
                for key_elem in root.findall('g:key', ns):
                    key_map[key_elem.get('id', '')] = key_elem.get('attr.name', '')

                def get_data(element, key_name):
                    for data in element.findall('g:data', ns):
                        if key_map.get(data.get('key', '')) == key_name:
                            return (data.text or '').strip().strip('"')
                    return ''

                # Parse nodes (entities)
                for node in root.findall('.//g:node', ns):
                    node_id = node.get('id', '').strip('"')
                    if not node_id:
                        continue

                    entity_name = get_data(node, 'entity_name') or node_id
                    description = get_data(node, 'description')
                    if '<SEP>' in description:
                        description = description.split('<SEP>')[0].strip()

                    entities.append({
                        "id": node_id,
                        "name": entity_name,
                        "type": get_data(node, 'entity_type') or 'CIVIC_ENTITY',
                        "description": description[:400] if description else '',
                        "source_commune": commune_id
                    })

            except Exception as e:
                logger.warning(f"GraphML parse error for {commune_id}: {e}")

            return entities, commune_id

        # Parallel GraphML loading
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=10) as executor:
            graphml_tasks = [
                loop.run_in_executor(executor, parse_graphml_for_query, c)
                for c in target_communes
            ]
            graphml_results = await asyncio.gather(*graphml_tasks)

        # Aggregate entities
        all_entities = []
        communes_loaded = []
        for entities, commune_id in graphml_results:
            all_entities.extend(entities)
            if entities:
                communes_loaded.append(commune_id)

        logger.info(f"Loaded {len(all_entities)} entities from {len(communes_loaded)} communes")

        # ============================================================
        # STEP 2: Load community reports (pre-computed, no LLM)
        # ============================================================
        all_communities = []
        for commune in target_communes:
            communities = load_community_reports(commune['id'])
            all_communities.extend(communities)

        logger.info(f"Loaded {len(all_communities)} community reports")

        # ============================================================
        # STEP 3: Build aggregated context
        # ============================================================
        context = build_context_from_graph(all_entities, all_communities, query)

        if not context.strip():
            return json.dumps({
                "success": False,
                "error": "No relevant context found for query",
                "communes_checked": len(target_communes)
            }, ensure_ascii=False)

        # ============================================================
        # STEP 4: ONE LLM call with combined context
        # ============================================================
        prompt = f"""Tu es un analyste expert des contributions citoyennes du Grand Débat National 2019.
Analyse les données de {len(communes_loaded)} communes de Charente-Maritime et réponds à la question.

QUESTION: {query}

CONTEXTE DU GRAPHE DE CONNAISSANCES:
{context}

INSTRUCTIONS:
- Synthétise les informations de plusieurs communes
- Cite des exemples spécifiques avec leurs communes d'origine
- Reste factuel et basé sur les données fournies
- Réponds en français

RÉPONSE:"""

        logger.info(f"Making ONE LLM call with {len(context)} chars context...")
        answer = await gpt_5_nano_complete(prompt, max_tokens=8192)

        # ============================================================
        # Build response with provenance
        # ============================================================
        response = {
            "success": True,
            "query": query,
            "mode": mode.value,
            "communes_queried": len(communes_loaded),
            "communes_list": communes_loaded,
            "answer": answer,
        }

        if include_sources:
            # Feature 007-mcp-graph-optimization T007: Parallel chunk loading
            # Extract chunk IDs from entities
            chunk_requests = []
            for entity in all_entities[:50]:
                chunk_ids = entity.get("chunk_ids", [])
                for chunk_id in chunk_ids[:3]:  # Max 3 chunks per entity
                    chunk_requests.append((chunk_id, entity.get("source_commune", "")))

            # Load chunks in parallel (grouped by commune, each file opened once)
            source_quotes = await load_chunks_parallel(chunk_requests)

            # Deduplicate by chunk ID
            seen_ids = set()
            unique_quotes = []
            for quote in source_quotes:
                if quote["id"] not in seen_ids:
                    seen_ids.add(quote["id"])
                    unique_quotes.append(quote)

            response["provenance"] = {
                "data_source": "Grand Débat National 2019",
                "total_entities": len(all_entities),
                "total_communities": len(all_communities),
                "entities": all_entities[:50],  # Top 50 for response size
                "communities": all_communities[:20],
                "source_quotes": unique_quotes[:20],  # Top 20 chunks
                "relationships": []  # Query_all doesn't track explicit paths
            }

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Query all error: {e}")
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool(
    name="grand_debat_query_fast",
    annotations={
        "title": "Fast Query All Communes (<10s)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def grand_debat_query_fast(
    query: Annotated[str, Field(description="Question about citizen contributions (French)", min_length=3)],
    max_communes: Annotated[int, Field(description="Maximum communes to query", ge=1, le=50)] = 50,
    include_sources: Annotated[bool, Field(description="Include source quotes for provenance")] = True
) -> str:
    """
    FAST query (<10s) using DUAL-STRATEGY retrieval + multi-hop traversal.

    **Performance**: Skips embedding search entirely. Uses pre-computed community
    reports AND global entity search for corpus-wide coverage. Target latency: <10 seconds.

    Architecture (DUAL-STRATEGY for full corpus coverage):
    1a. Community selection via keyword matching (<100ms) - thematic context
    1b. Global entity keyword search (<100ms) - corpus-wide coverage
    2. Combine seeds from both strategies (instant)
    3. Multi-hop BFS expansion across ALL communes (50ms)
    4. Single LLM call with aggregated context (3-5s)

    Args:
        query: Question in French about the Grand Débat National
        max_communes: Maximum number of communes to include (default: 50)

    Returns:
        JSON with answer, provenance, and performance metrics
    """
    import time
    from nano_graphrag._llm import gpt_5_nano_complete
    start_time = time.time()

    try:
        # Get total communes for provenance tracking
        index = await ensure_graph_index_initialized()
        total_communes_available = len(index._loaded_communes)

        # Phase 1a: Community selection via keyword matching (<100ms with cache)
        # Provides thematic context and summaries
        phase1a_start = time.time()
        communities = await select_communities_by_keywords(query, max_communes)
        phase1a_time = time.time() - phase1a_start

        # Phase 1b: Global entity keyword search across ALL communes (<100ms)
        # FIX for 9-commune limitation: ensures corpus-wide coverage
        phase1b_start = time.time()
        global_entities = await search_entities_globally(query, max_results=100)
        phase1b_time = time.time() - phase1b_start

        # Combine seed entities from both strategies
        phase2_start = time.time()

        # Strategy A: Seeds from communities (thematic clusters)
        community_seeds = extract_entities_from_communities(communities) if communities else []
        community_commune_ids = set(c['commune_id'] for c in communities) if communities else set()

        # Strategy B: Seeds from global entity search (corpus-wide)
        global_seeds = [e['id'] for e in global_entities[:50]]
        global_commune_ids = set(e['commune'] for e in global_entities)

        # Merge seeds (deduplicated)
        all_seeds = list(set(community_seeds + global_seeds))

        # Track all communes that contributed data
        all_commune_ids = community_commune_ids | global_commune_ids

        phase2_time = time.time() - phase2_start

        # Check if we have any seeds
        if not all_seeds:
            return json.dumps({
                "success": False,
                "error": "Aucune entité pertinente trouvée pour cette requête.",
                "suggestion": "Essayez des mots-clés plus généraux (fiscalité, écologie, démocratie...)",
                "provenance": {
                    "communes_searched": total_communes_available,
                    "communes_with_results": 0
                }
            }, ensure_ascii=False)

        # Phase 3: Multi-hop expansion across ALL communes (no filtering!)
        # FIX: Pass None instead of commune_ids to allow cross-commune traversal
        # DEEP TRAVERSAL: max_hops=3 to reach chunks (entity → relation → entity → chunk)
        # This is fast (<100ms) since GraphIndex is pre-loaded
        phase3_start = time.time()
        entities, paths = await expand_via_index(all_seeds, None, max_hops=3, max_results=500)
        phase3_time = time.time() - phase3_start

        # Track communes from expanded results
        expanded_commune_ids = set(e.get('commune', '') for e in entities if e.get('commune'))
        final_commune_ids = all_commune_ids | expanded_commune_ids

        # Combined phase 1 time for backward compatibility
        phase1_time = phase1a_time + phase1b_time

        # Phase 4: Build context + LLM call (3-5s)
        phase4_start = time.time()

        # Get source chunks via graph traversal from SEED entities (not expanded)
        # FIX: Expanded entities include chunks themselves (which don't have HAS_SOURCE edges)
        # Use all_seeds (original entity IDs like 'FISCALITÉ') which DO have HAS_SOURCE edges
        source_quotes = []
        seen_chunks = set()

        # DEBUG: Log seed entities to investigate chunk retrieval
        logger.info(f"DEBUG: Processing {len(all_seeds)} seed entities for chunks")
        logger.info(f"DEBUG: First 10 seeds: {all_seeds[:10]}")

        chunks_found_per_seed = 0
        for seed_id in all_seeds[:100]:
            chunks = index.get_chunks_for_entity(seed_id)
            if chunks:
                chunks_found_per_seed += 1
                logger.info(f"DEBUG: Seed '{seed_id}' has {len(chunks)} chunks")

            for chunk in chunks[:2]:  # Max 2 chunks per seed entity
                if chunk.chunk_id not in seen_chunks:
                    seen_chunks.add(chunk.chunk_id)
                    source_quotes.append({
                        "id": chunk.chunk_id,
                        "content": chunk.content,
                        "commune": chunk.commune,
                        "contribution_type": chunk.contribution_type,
                        "demographic": chunk.demographic,
                        "chunk_order": chunk.chunk_order_index,
                    })
                if len(source_quotes) >= 15:
                    break
            if len(source_quotes) >= 15:
                break

        logger.info(f"DEBUG: Retrieved {len(source_quotes)} source_quotes from {chunks_found_per_seed} seeds with chunks")

        # Build context for LLM - Optimized for massive ontological expansion
        # With 100 entities + 5-hop expansion, prioritize signal over noise
        context_parts = []

        # PRIORITY 1: Citizen quotes FIRST (most specific, grounded evidence)
        # INCREASED to 20 for better coverage from expanded small worlds
        if source_quotes:
            context_parts.append("## Citations citoyennes (texte source)\n\n")
            for q in source_quotes[:20]:  # Increased from 15 to 20
                commune = q.get('commune', 'Inconnu')
                content = q.get('content', '')[:600]
                context_parts.append(f"**[{commune}]**: \"{content}\"\n\n")

        # PRIORITY 2: Thematic summaries (broader context)
        # KEEP at 8 for balance
        context_parts.append("\n## Synthèses thématiques\n")
        for c in communities[:8]:
            context_parts.append(f"**[{c['commune_id']}] {c['title']}**\n")
            context_parts.append(f"{c['summary'][:300]}\n\n")

        # PRIORITY 3: Key entities with ontological type annotation
        # REDUCED from 40 to 25 - with massive expansion, less is more (critical entities only)
        context_parts.append("## Entités civiques clés\n")
        for e in entities[:25]:
            desc = e.get('description', '')[:150]
            entity_type = e.get('type', 'UNKNOWN')
            context_parts.append(f"- **{e['name']}** (type: {entity_type}, commune: {e['commune']}): {desc}\n")

        # PRIORITY 4: Discovered relationships
        # KEEP at 15 for inter-entity pattern discovery
        context_parts.append("\n## Relations découvertes\n")
        for p in paths[:15]:
            context_parts.append(f"- {p['source']} --[{p['type']}]--> {p['target']}\n")

        context = "".join(context_parts)

        prompt = f"""Tu es un expert des contributions citoyennes du Grand Débat National. Réponds directement à la question posée en te basant sur le graphe de connaissances.

QUESTION: {query}

GRAPHE DE CONNAISSANCES:
{context}

INSTRUCTIONS:

1. RÉPONDS DIRECTEMENT: Commence par répondre à la question. Si plusieurs communes sont concernées, détaille par commune.

2. SOURCES: Cite les communes et entités pertinentes entre parenthèses: (Commune: ENTITÉ)
   Exemple: "Les impôts sont une préoccupation majeure (Andilly: THEMATIQUE_Fiscalité, Rochefort: DOLEANCE_ImpôtsFonciers)"

3. ADAPTE LA LONGUEUR:
   - Question spécifique (1 commune, 1 fait) → Réponse brève (50-200 mots)
   - Question large (thème transversal) → Détaille par commune (50-100 mots × communes concernées)
   - Question introuvable → "Information non trouvée dans les {len(final_commune_ids)} communes" (1 phrase)

4. STRUCTURE ADAPTATIVE:
   Si plusieurs communes concernées:
   - Introduction: synthèse en 2-3 phrases
   - Par commune: **[Commune]**: [faits] (sources: entités)
   - Si pertinent: synthèse transversale des patterns

   Si 1 seule commune ou fait simple:
   - Réponse directe avec source

5. PAS DE MÉTHODOLOGIE:
   - Ne pas expliquer le protocole de recherche
   - Ne pas lister les types d'entités explorées
   - Ne pas suggérer de reformulation
   - Si pas de donnée, dire simplement "Non documenté"

RÉPONSE:"""

        answer = await gpt_5_nano_complete(prompt, max_tokens=8192)
        phase4_time = time.time() - phase4_start

        total_time = time.time() - start_time

        response = {
            "success": True,
            "query": query,
            "answer": answer,
            "performance": {
                "total_seconds": round(total_time, 2),
                "target_met": total_time < 10.0,
                "phases": {
                    "community_selection": round(phase1a_time, 3),
                    "global_entity_search": round(phase1b_time, 3),
                    "seed_merging": round(phase2_time, 3),
                    "multihop_expansion": round(phase3_time, 3),
                    "llm_call": round(phase4_time, 3)
                }
            },
            "provenance": {
                # Full entity data for graph visualization (Constitution Principle I)
                # No limit - return complete subgraph from multi-hop traversal
                "entities": [
                    {
                        "id": e.get('name', f"entity-{i}"),
                        "name": e.get('name', ''),
                        "type": e.get('type', 'CIVIC_ENTITY'),
                        "description": e.get('description', '')[:200],
                        "source_commune": e.get('commune', ''),
                        "importance_score": e.get('importance_score', 0.5)
                    }
                    for i, e in enumerate(entities)
                ],
                # Full relationship data for graph edges
                # No limit - return all paths from BFS expansion
                "relationships": [
                    {
                        "source": p.get('source', ''),
                        "target": p.get('target', ''),
                        "type": p.get('type', 'RELATED_TO'),
                        "description": p.get('description', ''),
                        "weight": p.get('weight', 1.0)
                    }
                    for p in paths
                ],
                # Community summaries - no limit
                "communities": [
                    {
                        "title": c.get('title', ''),
                        "summary": c.get('summary', '')[:300],
                        "commune": c.get('commune_id', '')
                    }
                    for c in communities
                ],
                # Statistics - Full provenance tracking
                "stats": {
                    "communities_matched": len(communities) if communities else 0,
                    "seed_entities_community": len(community_seeds),
                    "seed_entities_global": len(global_seeds),
                    "seed_entities_total": len(all_seeds),
                    "expanded_entities": len(entities),
                    "relationship_paths": len(paths),
                    "communes_searched": total_communes_available,
                    "communes_with_results": len(final_commune_ids),
                    "communes": list(final_commune_ids)
                }
            }
        }

        # Add source_quotes to provenance (already collected via graph traversal above)
        # Truncate content for JSON response (full content was used in LLM prompt)
        logger.info(f"DEBUG: include_sources={include_sources}, source_quotes={len(source_quotes)}")
        if include_sources and source_quotes:
            logger.info(f"DEBUG: Adding {len(source_quotes)} source_quotes to response")
            response["provenance"]["source_quotes"] = [
                {
                    "id": q["id"],
                    "content": q["content"][:500],  # Truncate for response
                    "commune": q["commune"],
                    "contribution_type": q.get("contribution_type"),
                    "demographic": q.get("demographic"),
                    "chunk_order": q.get("chunk_order"),
                }
                for q in source_quotes
            ]
            logger.info(f"DEBUG: Response has {len(response['provenance']['source_quotes'])} quotes")
        else:
            logger.warning(f"DEBUG: NOT adding quotes - include_sources={include_sources}")

        logger.info(f"Fast query completed in {total_time:.2f}s (target: <10s)")
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Fast query error: {e}")
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool(
    name="grand_debat_query_local_surgical",
    annotations={
        "title": "Query with Surgical RAG (Local Mode with Small Worlds)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def grand_debat_query_local_surgical(
    query: Annotated[str, Field(description="Question about citizen contributions (French)", min_length=3)],
    commune_id: Annotated[str, Field(description="Target commune for local mode query")] = "Angoulins",
    include_sources: Annotated[bool, Field(description="Include full provenance chain")] = True
) -> str:
    """
    SURGICAL RAG query using true LOCAL MODE with massive ontological expansion.

    **Architecture (Small Worlds Retrieval)**:
    - Uses QueryParam with mode="local" (NOT manual expansion)
    - Leverages configured settings: top_k=100, local_max_hops=5
    - Reconstitutes complete "petits mondes" with ontological coverage
    - Surgical prompt with end-to-end interpretability

    **Returns**: JSON with answer, provenance chain, and small worlds statistics
    """
    start_time = time.time()

    try:
        # Get commune path
        commune_path = get_commune_path(commune_id)
        if not commune_path:
            available = [c['id'] for c in list_communes()[:10]]
            return json.dumps({
                "success": False,
                "error": f"Commune '{commune_id}' not found",
                "available_communes": available
            }, ensure_ascii=False)

        # Import GraphRAG
        import sys
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from nano_graphrag import GraphRAG, QueryParam
        from nano_graphrag._llm import gpt_5_nano_complete

        # Get cached GraphRAG instance
        working_dir = str(commune_path)
        rag = _graphrag_cache.get(working_dir)
        if rag is None:
            rag = GraphRAG(
                working_dir=working_dir,
                best_model_func=gpt_5_nano_complete,
                cheap_model_func=gpt_5_nano_complete,
            )
            _graphrag_cache.put(working_dir, rag)

        # Use LOCAL MODE with our configured QueryParam defaults:
        # - top_k=100 (massive retrieval for ontological coverage)
        # - local_max_hops=5 (deep multi-hop for small worlds)
        # - Increased token limits for complete context
        # - Comprehensive response_type for detailed multi-commune analysis
        result = await rag.aquery(
            query,
            param=QueryParam(
                mode="local",
                return_provenance=include_sources,
                response_type="Comprehensive multi-commune analysis: 2500-5000 words total. Structure: Introduction (2-3 sentences) + ## Analyse par commune (one detailed paragraph per commune with provenance, 50-100 words each) + ## Synthèse transversale (patterns and variations across communes)"
            )
        )

        total_time = time.time() - start_time

        # Extract provenance for small worlds analysis (result is a dict)
        answer = ""
        provenance = {}

        if isinstance(result, dict):
            answer = result.get("answer", "")
            if include_sources:
                result_prov = result.get("provenance", {})
                entities = result_prov.get('entities', [])
                chunks = result_prov.get('source_quotes', [])  # FIXED: use 'source_quotes' not 'chunks'
                relationships = result_prov.get('relationships', [])

                # Analyze ontological coverage
                entity_types = {}
                for e in entities:
                    etype = e.get('type', 'UNKNOWN')  # FIXED: use 'type' not 'entity_type'
                    # Normalize by stripping quotes
                    normalized_type = etype.strip('"').strip("'")
                    entity_types[normalized_type] = entity_types.get(normalized_type, 0) + 1

                # Count unique communes in the small world
                communes_in_small_world = set(
                    c.get('commune', 'Unknown') for c in chunks if c.get('commune') != 'Unknown'
                )

                # Calculate ontological coverage
                CORE_CIVIC_ENTITY_TYPES = [
                    "PROPOSITION", "THEMATIQUE", "SERVICEPUBLIC", "DOLEANCE",
                    "ACTEURINSTITUTIONNEL", "OPINION", "CITOYEN", "CONCEPT",
                    "REFORMEDEMOCRATIQUE", "TERRITOIRE", "COMMUNE", "CONTRIBUTION"
                ]
                missing_types = [t for t in CORE_CIVIC_ENTITY_TYPES if t not in entity_types]
                coverage_pct = (len(CORE_CIVIC_ENTITY_TYPES) - len(missing_types)) / len(CORE_CIVIC_ENTITY_TYPES) * 100

                provenance = {
                    "entities": entities[:50],  # Sample for output size
                    "source_quotes": chunks[:20],
                    "relationships": relationships[:30],
                    "small_worlds_stats": {
                        "target_commune": commune_id,
                        "total_entities_retrieved": len(entities),
                        "total_chunks_retrieved": len(chunks),
                        "total_relationships": len(relationships),
                        "entity_type_coverage": entity_types,
                        "communes_in_small_world": list(communes_in_small_world),
                        "ontological_coverage_pct": round(coverage_pct, 1),
                        "missing_types": missing_types
                    }
                }

        response = {
            "success": True,
            "query": query,
            "answer": answer,
            "mode": "local",
            "architecture": "Surgical RAG with Small Worlds (top_k=100, local_max_hops=5)",
            "performance": {
                "total_seconds": round(total_time, 2),
                "query_mode": "local_surgical_rag"
            },
            "provenance": provenance if include_sources else None
        }

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Local surgical query error: {e}")
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": str(e),
            "commune_id": commune_id
        }, ensure_ascii=False)


@mcp.tool(
    name="grand_debat_query_all_surgical",
    annotations={
        "title": "Query ALL Communes in Parallel (56 Mini-Worlds)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def grand_debat_query_all_surgical(
    query: Annotated[str, Field(description="Question about citizen contributions (French)", min_length=3)],
    max_communes: Annotated[int, Field(description="Maximum communes to query in parallel", ge=1, le=56)] = 56
) -> str:
    """
    Query ALL communes in PARALLEL using local mode surgical RAG.

    **Architecture (56 Mini-Worlds in Parallel)**:
    - Queries up to 56 communes concurrently using asyncio.gather()
    - Each commune creates its own mini-world with top_k=100, local_max_hops=5
    - Aggregates results from all mini-worlds
    - Much faster than sequential queries (~30-60s vs 30+ minutes)

    **Returns**: JSON with aggregated results and mini-worlds statistics
    """
    start_time = time.time()

    try:
        # Get all communes
        all_communes = list_communes()
        communes_to_query = [c['id'] for c in all_communes[:max_communes]]

        logger.info(f"Starting parallel surgical query across {len(communes_to_query)} communes...")

        # Query all communes in parallel
        tasks = [
            grand_debat_query_local_surgical(query, commune_id, include_sources=True)
            for commune_id in communes_to_query
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        mini_worlds = []
        total_entities = 0
        total_chunks = 0
        total_relationships = 0
        all_answers = []

        for commune_id, result_str in zip(communes_to_query, results):
            if isinstance(result_str, Exception):
                logger.warning(f"Commune {commune_id} failed: {result_str}")
                continue

            try:
                result = json.loads(result_str)
                if result.get('success'):
                    prov = result.get('provenance', {}) or {}
                    stats = prov.get('small_worlds_stats', {}) or {}

                    entities = stats.get('total_entities_retrieved', 0)
                    chunks = stats.get('total_chunks_retrieved', 0)
                    rels = stats.get('total_relationships', 0)

                    mini_worlds.append({
                        'commune': commune_id,
                        'entities': entities,
                        'chunks': chunks,
                        'relationships': rels,
                        'coverage_pct': stats.get('ontological_coverage_pct', 0)
                    })

                    total_entities += entities
                    total_chunks += chunks
                    total_relationships += rels
                    all_answers.append(result.get('answer', ''))
            except Exception as e:
                logger.warning(f"Failed to parse result for {commune_id}: {e}")

        total_time = time.time() - start_time

        # Create aggregated answer by combining all individual answers
        aggregated_answer = "\n\n---\n\n".join(all_answers) if all_answers else "Aucune réponse générée"

        # Collect unique communes with results
        communes_with_results = list(set(mw['commune'] for mw in mini_worlds))

        # Create aggregated response
        response = {
            "success": True,
            "query": query,
            "architecture": "Parallel Surgical RAG (56 Mini-Worlds)",
            "mini_worlds_count": len(mini_worlds),
            "aggregated_answer": aggregated_answer,
            "aggregated_stats": {
                "total_communes_queried": len(communes_to_query),
                "successful_queries": len(mini_worlds),
                "failed_queries": len(communes_to_query) - len(mini_worlds),
                "total_entities": total_entities,
                "total_chunks": total_chunks,
                "total_relationships": total_relationships,
                "avg_entities_per_commune": round(total_entities / len(mini_worlds), 1) if mini_worlds else 0,
                "avg_chunks_per_commune": round(total_chunks / len(mini_worlds), 1) if mini_worlds else 0,
                "avg_ontological_coverage": round(sum(mw['coverage_pct'] for mw in mini_worlds) / len(mini_worlds), 1) if mini_worlds else 0,
                "communes_with_results": communes_with_results
            },
            "mini_worlds": mini_worlds[:10],  # Sample first 10
            "answers_sample": all_answers[:3],  # Sample first 3 answers
            "performance": {
                "total_seconds": round(total_time, 2),
                "communes_queried": len(mini_worlds),
                "queries_per_second": round(len(mini_worlds) / total_time, 2) if total_time > 0 else 0
            }
        }

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Parallel surgical query error: {e}")
        import traceback
        traceback.print_exc()
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

    FAST VERSION: Reads directly from GraphML files (not JSON) using parallel I/O.
    Designed for instant graph loading (200+ nodes in <3 seconds).

    Perfect for:
    - Initial page load with full graph visualization
    - Exploring entity landscape before semantic queries
    - Performance-critical applications

    Args:
        max_communes: How many communes to load (default: 50 = ALL)
        include_relationships: Whether to include edge relationships (default: True)

    Returns:
        JSON with all entities and relationships across communes
    """
    import xml.etree.ElementTree as ET
    from concurrent.futures import ThreadPoolExecutor
    import asyncio

    def parse_graphml_file(commune_info: dict) -> tuple:
        """Parse a single GraphML file - runs in thread pool for parallelism."""
        commune_id = commune_info['id']
        commune_path = get_commune_path(commune_id)
        if not commune_path:
            return [], [], commune_id

        graphml_file = commune_path / "graph_chunk_entity_relation.graphml"
        if not graphml_file.exists():
            return [], [], commune_id

        entities = []
        relationships = []

        try:
            tree = ET.parse(graphml_file)
            root = tree.getroot()

            # GraphML namespace
            ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}

            # Build key mapping from header
            key_map = {}
            for key_elem in root.findall('g:key', ns):
                key_id = key_elem.get('id', '')
                key_name = key_elem.get('attr.name', '')
                key_map[key_id] = key_name

            # Helper to get data value by key name
            def get_data(element, key_name):
                for data in element.findall('g:data', ns):
                    key_id = data.get('key', '')
                    if key_map.get(key_id) == key_name:
                        return (data.text or '').strip().strip('"')
                return ''

            # Parse nodes (entities) - FAST: direct from GraphML, no JSON!
            for node in root.findall('.//g:node', ns):
                node_id = node.get('id', '').strip('"')
                if not node_id:
                    continue

                entity_name = get_data(node, 'entity_name') or node_id
                entity_type = get_data(node, 'entity_type') or 'CIVIC_ENTITY'
                description = get_data(node, 'description')

                # Clean up description (take first part if multiple <SEP>)
                if '<SEP>' in description:
                    description = description.split('<SEP>')[0].strip()

                entities.append({
                    "id": node_id,
                    "name": entity_name,
                    "type": entity_type,
                    "description": description[:500] if description else '',  # Limit for performance
                    "source_commune": commune_id,
                    "importance_score": 0.5
                })

            # Parse edges (relationships)
            if include_relationships:
                entity_ids = {e['id'] for e in entities}
                for edge in root.findall('.//g:edge', ns):
                    source_id = edge.get('source', '').strip('"')
                    target_id = edge.get('target', '').strip('"')

                    # Only include relationships between entities we loaded
                    if source_id in entity_ids and target_id in entity_ids:
                        # Try 'type' first (matches GraphML attr.name), then fallbacks
                        rel_type = get_data(edge, 'type') or get_data(edge, 'relationship_type') or get_data(edge, 'label') or 'RELATED_TO'
                        weight_str = get_data(edge, 'weight')
                        try:
                            weight = float(weight_str) if weight_str else 1.0
                        except ValueError:
                            weight = 1.0

                        relationships.append({
                            "source": source_id,
                            "target": target_id,
                            "type": rel_type,
                            "weight": weight,
                            "description": get_data(edge, 'description')[:200] if get_data(edge, 'description') else '',
                            "source_commune": commune_id
                        })

        except Exception as e:
            logger.warning(f"Failed to parse GraphML for {commune_id}: {e}")

        return entities, relationships, commune_id

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

        logger.info(f"Loading full graph from {len(target_communes)} communes (parallel GraphML)")

        # PARALLEL: Load all GraphML files concurrently using thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = [
                loop.run_in_executor(executor, parse_graphml_file, commune_info)
                for commune_info in target_communes
            ]
            results = await asyncio.gather(*tasks)

        # Merge results from all communes
        all_entities = []
        all_relationships = []
        communes_loaded = []

        for entities, relationships, commune_id in results:
            all_entities.extend(entities)
            all_relationships.extend(relationships)
            if entities:  # Only count if we got data
                communes_loaded.append(commune_id)

        logger.info(f"Loaded {len(all_entities)} entities, {len(all_relationships)} relationships from {len(communes_loaded)} communes")

        # Load text chunks for source_quotes
        source_quotes = []
        for commune_id in communes_loaded:
            commune_path = get_commune_path(commune_id)
            if not commune_path:
                continue

            chunks_file = commune_path / "kv_store_text_chunks.json"
            if not chunks_file.exists():
                continue

            try:
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    text_chunks = json.load(f)

                # Take first 10 chunks from each commune (or adjust based on need)
                for chunk_id, chunk_data in list(text_chunks.items())[:10]:
                    source_quotes.append({
                        "id": chunk_id,
                        "content": chunk_data.get("content", "")[:500],
                        "commune": chunk_data.get("commune", commune_id)
                    })
            except Exception as e:
                logger.warning(f"Error loading chunks for {commune_id}: {e}")

        # Limit to 50 total chunks for performance
        source_quotes = source_quotes[:50]

        return json.dumps({
            "success": True,
            "total_communes": len(communes_loaded),
            "total_entities": len(all_entities),
            "total_relationships": len(all_relationships),
            "communes_loaded": communes_loaded,
            "data_source": "Grand Débat National 2019",
            "provenance": {
                "entities": all_entities,
                "relationships": all_relationships,
                "source_quotes": source_quotes,
                "communities": []  # Use grand_debat_get_communities for community data
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
