#!/usr/bin/env python3
"""
Test script to visualize the context built for grand_debat_query_all.
Shows what gets sent to the LLM before aggregation.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from collections import defaultdict

# Configuration
DATA_PATH = os.environ.get('GRAND_DEBAT_DATA_PATH', './law_data')


def list_communes():
    """List all available communes with statistics."""
    base_path = Path(DATA_PATH)
    if not base_path.exists():
        return []

    communes = []
    for item in base_path.iterdir():
        if item.is_dir():
            entity_count = 0
            community_count = 0

            # Count entities
            vdb_file = item / "vdb_entities.json"
            if vdb_file.exists():
                try:
                    with open(vdb_file, 'r') as f:
                        data = json.load(f)
                        entity_count = len(data) if isinstance(data, dict) else 0
                except:
                    pass

            # Count communities
            comm_file = item / "kv_store_community_reports.json"
            if comm_file.exists():
                try:
                    with open(comm_file, 'r') as f:
                        data = json.load(f)
                        community_count = len(data) if isinstance(data, dict) else 0
                except:
                    pass

            communes.append({
                'id': item.name,
                'name': item.name.replace('_', ' '),
                'entity_count': entity_count,
                'community_count': community_count
            })

    return sorted(communes, key=lambda x: x['name'])


def load_community_reports(commune_id: str):
    """Load pre-computed community reports."""
    commune_path = Path(DATA_PATH) / commune_id
    if not commune_path.exists():
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
            for c in list(data.values())[:5]
        ]
    except Exception as e:
        return []


def build_context_from_graph(entities, communities, query, max_context_chars=12000):
    """Build LLM context from aggregated graph data."""
    import re

    context_parts = []
    current_size = 0

    # Add metadata
    context_parts.append(f"# Base de connaissances du Grand Débat National\n\n")
    current_size += len(context_parts[-1])

    # Find relevant entities using keyword matching
    query_lower = query.lower()
    query_keywords = set(re.findall(r'\b\w{3,}\b', query_lower))

    def relevance_score(entity):
        name = (entity.get('name') or '').lower()
        desc = (entity.get('description') or '').lower()
        score = 0
        for kw in query_keywords:
            if kw in name:
                score += 3
            if kw in desc:
                score += 1
        return score

    # Score and filter entities
    scored_entities = [(e, relevance_score(e)) for e in entities]
    relevant_entities = [e for e, score in sorted(scored_entities, key=lambda x: x[1], reverse=True) if score > 0][:100]

    # If no keyword matches, use first 50 entities
    if not relevant_entities:
        relevant_entities = entities[:50]

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

    # Add community summaries
    if communities:
        context_parts.append("\n## Synthèses thématiques par commune\n")
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

    return ''.join(context_parts)


async def test_context_visualization(query: str = "Quelles sont les principales préoccupations des citoyens ?", max_communes: int = 5):
    """
    Reproduces the context building logic from grand_debat_query_all
    without making the LLM call, to show what context is built.

    Args:
        query: Test query
        max_communes: Number of communes to include (default: 5 for testing)
    """
    print("=" * 80)
    print(f"TEST: Context Visualization for grand_debat_query_all")
    print("=" * 80)
    print(f"Query: {query}")
    print(f"Max communes: {max_communes}")
    print()

    # ============================================================
    # STEP 1: Load communes and GraphML data
    # ============================================================
    print("STEP 1: Loading communes...")
    all_communes = list_communes()
    if not all_communes:
        print("ERROR: No communes found")
        return

    # Sort by entity count and take top N
    sorted_communes = sorted(all_communes, key=lambda x: x.get('entity_count', 0), reverse=True)
    target_communes = sorted_communes[:max_communes]

    print(f"  - Total communes available: {len(all_communes)}")
    print(f"  - Target communes (top {max_communes} by entity count):")
    for c in target_communes:
        print(f"    * {c['id']} ({c.get('entity_count', 0)} entities)")
    print()

    # Load GraphML entities
    print("STEP 2: Loading GraphML entities...")
    import xml.etree.ElementTree as ET

    all_entities = []
    communes_loaded = []

    for commune in target_communes:
        commune_id = commune['id']
        commune_path = Path(DATA_PATH) / commune_id
        graphml_file = commune_path / "graph_chunk_entity_relation.graphml"

        if not graphml_file.exists():
            print(f"  - {commune_id}: GraphML not found")
            continue

        try:
            tree = ET.parse(graphml_file)
            root = tree.getroot()
            ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}

            count = 0
            for node in root.findall('.//g:node', ns):
                node_id = node.get('id', '').strip('"')

                def get_data(node, key):
                    elem = node.find(f"./g:data[@key='{key}']", ns)
                    return elem.text.strip() if elem is not None and elem.text else None

                entity_name = get_data(node, 'entity_name') or node_id
                entity_type = get_data(node, 'entity_type')
                description = get_data(node, 'description')

                if entity_name and entity_name.strip():
                    all_entities.append({
                        'name': entity_name,
                        'type': entity_type,
                        'description': (description or '')[:300],
                        'source_commune': commune_id
                    })
                    count += 1

            communes_loaded.append(commune_id)
            print(f"  - {commune_id}: {count} entities loaded")

        except Exception as e:
            print(f"  - {commune_id}: ERROR - {e}")

    print(f"  - Total entities loaded: {len(all_entities)}")
    print()

    # ============================================================
    # STEP 3: Load community reports
    # ============================================================
    print("STEP 3: Loading community reports...")
    all_communities = []
    for commune in target_communes:
        communities = load_community_reports(commune['id'])
        all_communities.extend(communities)
        print(f"  - {commune['id']}: {len(communities)} communities")

    print(f"  - Total communities: {len(all_communities)}")
    print()

    # ============================================================
    # STEP 4: Build aggregated context
    # ============================================================
    print("STEP 4: Building aggregated context...")
    context = build_context_from_graph(all_entities, all_communities, query)

    context_length = len(context)
    context_tokens_estimate = context_length // 4  # Rough estimate: 1 token ≈ 4 chars

    print(f"  - Context length: {context_length:,} characters")
    print(f"  - Estimated tokens: {context_tokens_estimate:,}")
    print()

    # ============================================================
    # STEP 5: Build prompt (what would be sent to LLM)
    # ============================================================
    print("STEP 5: Building final prompt...")
    prompt = f"""CONTEXTE:
{context}

QUESTION: {query}

INSTRUCTIONS:
- Synthétise les informations de plusieurs communes
- Cite des exemples spécifiques avec leurs communes d'origine
- Reste factuel et basé sur les données fournies
- Réponds en français

RÉPONSE:"""

    prompt_length = len(prompt)
    prompt_tokens_estimate = prompt_length // 4

    print(f"  - Prompt length: {prompt_length:,} characters")
    print(f"  - Estimated tokens: {prompt_tokens_estimate:,}")
    print()

    # ============================================================
    # Display context preview
    # ============================================================
    print("=" * 80)
    print("CONTEXT PREVIEW (first 2000 characters)")
    print("=" * 80)
    print(context[:2000])
    print("\n... [truncated] ...\n")

    print("=" * 80)
    print("CONTEXT PREVIEW (last 1000 characters)")
    print("=" * 80)
    print(context[-1000:])
    print()

    # ============================================================
    # Statistics
    # ============================================================
    print("=" * 80)
    print("STATISTICS")
    print("=" * 80)
    print(f"Communes included: {len(communes_loaded)} / {max_communes}")
    print(f"Total entities: {len(all_entities)}")
    print(f"Total communities: {len(all_communities)}")
    print(f"Context size: {context_length:,} chars (~{context_tokens_estimate:,} tokens)")
    print(f"Prompt size: {prompt_length:,} chars (~{prompt_tokens_estimate:,} tokens)")
    print(f"max_tokens for response: 8192 tokens")
    print()

    # Calculate coverage
    print("=" * 80)
    print("POTENTIAL ISSUES")
    print("=" * 80)

    if context_tokens_estimate > 12000:
        print("⚠️  WARNING: Context is very large (>12k tokens)")
        print("   This may lead to information loss in the aggregated response")

    if prompt_tokens_estimate + 8192 > 32000:
        print("⚠️  WARNING: Total tokens (prompt + response) may exceed model limits")
        print(f"   Prompt: ~{prompt_tokens_estimate:,} + Response: 8192 = ~{prompt_tokens_estimate + 8192:,} tokens")

    print()
    print("💡 RECOMMENDATION:")
    print("   Consider using grand_debat_query_all_surgical instead,")
    print("   which queries each commune separately and concatenates responses")
    print("   without LLM aggregation (preserves all information)")
    print()

    # Save full context to file for inspection
    output_file = "/tmp/context_visualization.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("FULL CONTEXT\n")
        f.write("=" * 80 + "\n\n")
        f.write(context)
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("FULL PROMPT\n")
        f.write("=" * 80 + "\n\n")
        f.write(prompt)

    print(f"✅ Full context saved to: {output_file}")
    print()


if __name__ == "__main__":
    # Parse command line arguments
    query = "Quelles sont les principales préoccupations des citoyens sur les transports ?"
    max_communes = 5

    if len(sys.argv) > 1:
        query = sys.argv[1]
    if len(sys.argv) > 2:
        max_communes = int(sys.argv[2])

    asyncio.run(test_context_visualization(query, max_communes))
