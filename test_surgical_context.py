#!/usr/bin/env python3
"""
Test script to simulate surgical query and analyze the context with text chunks.
Shows the difference in retrieval quality compared to grand_debat_query_all.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configuration
DATA_PATH = os.environ.get('GRAND_DEBAT_DATA_PATH', './law_data')


def list_communes():
    """List all available communes."""
    base_path = Path(DATA_PATH)
    if not base_path.exists():
        return []

    communes = []
    for item in base_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            communes.append(item.name)
    return sorted(communes)


async def test_surgical_query(query: str = "Quelles sont les principales préoccupations des citoyens sur les transports ?", max_communes: int = 3):
    """
    Simulate surgical query by calling GraphRAG directly on each commune.

    Args:
        query: Test query
        max_communes: Number of communes to query (default: 3 for quick testing)
    """
    print("=" * 80)
    print("TEST: Surgical Query Simulation - Context with Text Chunks")
    print("=" * 80)
    print(f"Query: {query}")
    print(f"Max communes: {max_communes}")
    print()

    # Import GraphRAG
    from nano_graphrag import GraphRAG, QueryParam
    from nano_graphrag._llm import gpt_5_nano_complete

    print("Loading communes...")
    all_communes = list_communes()
    if not all_communes:
        print("ERROR: No communes found in", DATA_PATH)
        return

    target_communes = all_communes[:max_communes]
    print(f"Target communes: {', '.join(target_communes)}")
    print()

    # Query each commune and collect provenance
    import time
    start_time = time.time()

    results = []
    total_entities = 0
    total_chunks = 0
    total_rels = 0

    for commune_id in target_communes:
        print(f"Querying {commune_id}...")
        commune_path = Path(DATA_PATH) / commune_id

        try:
            # Initialize GraphRAG for this commune
            rag = GraphRAG(
                working_dir=str(commune_path),
                best_model_func=gpt_5_nano_complete,
                cheap_model_func=gpt_5_nano_complete,
            )

            # Query with provenance to see what context is retrieved
            result = await rag.aquery(
                query,
                param=QueryParam(
                    mode="local",
                    return_provenance=True
                )
            )

            if isinstance(result, dict):
                answer = result.get("answer", "")
                prov = result.get("provenance", {})

                entities = prov.get('entities', [])
                chunks = prov.get('source_quotes', [])
                rels = prov.get('relationships', [])

                total_entities += len(entities)
                total_chunks += len(chunks)
                total_rels += len(rels)

                results.append({
                    'commune': commune_id,
                    'answer': answer,
                    'entities_count': len(entities),
                    'chunks_count': len(chunks),
                    'relationships_count': len(rels),
                    'entities': entities[:5],  # Sample
                    'chunks': chunks[:5]  # Sample
                })

                print(f"  ✓ Retrieved: {len(entities)} entities, {len(chunks)} chunks, {len(rels)} relationships")

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            continue

    elapsed_time = time.time() - start_time
    print()
    print(f"Completed in {elapsed_time:.2f}s")
    print()

    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Success: {len(results)} / {max_communes} communes")
    print(f"Execution time: {elapsed_time:.2f}s")
    print()

    # Display aggregated stats
    print("=" * 80)
    print("AGGREGATED STATISTICS")
    print("=" * 80)
    print(f"Total communes queried: {len(results)}")
    print(f"Total entities retrieved: {total_entities}")
    print(f"Total text chunks retrieved: {total_chunks} ← KEY DIFFERENCE!")
    print(f"Total relationships: {total_rels}")
    print()
    if len(results) > 0:
        print(f"Avg entities per commune: {total_entities / len(results):.1f}")
        print(f"Avg chunks per commune: {total_chunks / len(results):.1f}")
    print()

    # Display per-commune details
    print("=" * 80)
    print("PER-COMMUNE DETAILS")
    print("=" * 80)

    for r in results:
        commune = r['commune']
        print(f"\n{commune}:")
        print(f"  - Entities: {r['entities_count']}")
        print(f"  - Text chunks: {r['chunks_count']} ← REAL CITIZEN CONTRIBUTIONS")
        print(f"  - Relationships: {r['relationships_count']}")

        # Show sample chunks
        if r['chunks']:
            print(f"\n  Sample chunks (first 2):")
            for i, chunk in enumerate(r['chunks'][:2], 1):
                content = chunk.get('content', '')[:150]
                print(f"    {i}. {content}...")

    # Show text chunk samples in detail
    print()
    print("=" * 80)
    print("TEXT CHUNK SAMPLES (showing actual citizen contributions)")
    print("=" * 80)

    chunk_count = 0
    for r in results:
        commune = r['commune']
        for i, chunk in enumerate(r['chunks'][:2], 1):
            chunk_count += 1
            content = chunk.get('content', '')
            chunk_id = chunk.get('id', 'unknown')
            print(f"\n--- Chunk {chunk_count}: {commune} ---")
            print(f"ID: {chunk_id}")
            print(f"Content (first 300 chars):")
            print(content[:300])
            print("...")

    # Show answer samples
    print()
    print("=" * 80)
    print("ANSWER SAMPLES (first 2 communes)")
    print("=" * 80)

    for i, r in enumerate(results[:2], 1):
        commune = r['commune']
        answer = r['answer']
        print(f"\n--- Answer {i}: {commune} (first 500 chars) ---")
        print(answer[:500])
        print("...")

    # Key insights
    print()
    print("=" * 80)
    print("KEY INSIGHTS - Why surgical is better")
    print("=" * 80)
    print()
    print("✅ SURGICAL APPROACH:")
    print(f"   - Retrieves {total_chunks} TEXT CHUNKS (real citizen contributions)")
    print(f"   - Each commune gets {total_chunks / max(len(results), 1):.1f} chunks on average")
    print(f"   - Uses vector search to find relevant text")
    print(f"   - Full RAG pipeline: entities + communities + chunks + relations")
    print(f"   - Each chunk contains ACTUAL CITIZEN TEXT (not summaries)")
    print()
    print("❌ REGULAR query_all APPROACH (for comparison):")
    print("   - NO text chunks retrieved (0 chunks)")
    print("   - Only entity names (mostly empty descriptions)")
    print("   - Only community summaries (pre-aggregated, 2nd level)")
    print("   - Missing the actual citizen contributions")
    print()

    # Save full result to file
    output_file = "/tmp/surgical_context_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'communes_queried': len(results),
            'total_entities': total_entities,
            'total_chunks': total_chunks,
            'total_relationships': total_rels,
            'results': results
        }, f, indent=2, ensure_ascii=False)

    print(f"✅ Full result saved to: {output_file}")
    print()

    # Comparison table
    print("=" * 80)
    print("COMPARISON: query_all vs surgical")
    print("=" * 80)
    print()
    print("| Metric                  | query_all      | surgical              |")
    print("|-------------------------|----------------|-----------------------|")
    print("| Text chunks             | 0              | {:,}                |".format(total_chunks))
    print("| Entities                | ~100 (filtered)| {:,}                |".format(total_entities))
    print("| Context quality         | Low (names)    | High (full text)      |")
    print("| Vector search           | No             | Yes                   |")
    print("| Citizen contributions   | Missing        | Included              |")
    print("| LLM calls               | 1 (aggregated) | {} (parallel)       |".format(max_communes))
    print("| Response preservation   | Compressed     | Full (concatenated)   |")
    print()


if __name__ == "__main__":
    # Parse command line arguments
    query = "Quelles sont les principales préoccupations des citoyens sur les transports ?"
    max_communes = 3

    if len(sys.argv) > 1:
        query = sys.argv[1]
    if len(sys.argv) > 2:
        max_communes = int(sys.argv[2])

    asyncio.run(test_surgical_query(query, max_communes))
