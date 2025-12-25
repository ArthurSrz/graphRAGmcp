#!/usr/bin/env python3
"""
Re-extract entities with Grand Débat civic ontology.
This script bypasses the usual insert flow to force re-extraction
with the new entity types and relationship types defined in prompt.py.

Constitution Principle V: End-to-End Interpretability
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from dataclasses import asdict

# Add nano_graphrag to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from nano_graphrag.graphrag import GraphRAG
from nano_graphrag._llm import gpt_4o_mini_complete, openai_embedding
from nano_graphrag._op import extract_entities, generate_community_report
from nano_graphrag._storage import JsonKVStorage, NanoVectorDBStorage, NetworkXStorage
from nano_graphrag._utils import logger, TokenizerWrapper
from nano_graphrag.base import TextChunkSchema

DATA_PATH = Path("./law_data")

# Tracking
processed_communes = []
failed_communes = []

async def re_extract_single_commune(commune_path: Path) -> bool:
    """Re-extract entities for a single commune."""
    commune_name = commune_path.name
    print(f"\n{'='*60}")
    print(f"🏛️  Re-extracting: {commune_name}")
    print(f"{'='*60}")

    try:
        # Check if chunks exist
        chunks_file = commune_path / "kv_store_text_chunks.json"
        if not chunks_file.exists():
            print(f"  ⚠️  No chunks found in {commune_name}")
            return False

        # Load existing chunks
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)

        if not chunks_data:
            print(f"  ⚠️  Empty chunks file in {commune_name}")
            return False

        print(f"  📄 Found {len(chunks_data)} text chunks")

        # Initialize GraphRAG instance for this commune
        # Storages are auto-initialized in __post_init__
        rag = GraphRAG(
            working_dir=str(commune_path),
            best_model_func=gpt_4o_mini_complete,
            cheap_model_func=gpt_4o_mini_complete,
            embedding_func=openai_embedding,
        )

        # Prepare chunks in the expected format
        chunks: dict[str, TextChunkSchema] = {}
        for chunk_id, chunk_data in chunks_data.items():
            if isinstance(chunk_data, dict) and 'content' in chunk_data:
                chunks[chunk_id] = chunk_data

        if not chunks:
            print(f"  ⚠️  No valid chunks to process")
            return False

        print(f"  🔍 Extracting entities with Grand Débat ontology...")

        # Run entity extraction with new ontology
        maybe_new_kg = await extract_entities(
            chunks=chunks,
            knwoledge_graph_inst=rag.chunk_entity_relation_graph,
            entity_vdb=rag.entities_vdb,
            tokenizer_wrapper=rag.tokenizer_wrapper,
            global_config=asdict(rag),
            using_amazon_bedrock=False,
        )

        if maybe_new_kg is None:
            print(f"  ⚠️  No entities extracted")
            return False

        rag.chunk_entity_relation_graph = maybe_new_kg

        # Generate community reports
        print(f"  📊 Generating community reports...")
        await rag.chunk_entity_relation_graph.clustering(rag.graph_cluster_algorithm)
        await generate_community_report(
            rag.community_reports,
            rag.chunk_entity_relation_graph,
            rag.tokenizer_wrapper,
            asdict(rag)
        )

        # Commit to storage
        print(f"  💾 Saving to disk...")
        await rag._insert_done()

        # Count results
        nodes = await rag.chunk_entity_relation_graph.get_nodes_batch([])
        print(f"  ✅ Extracted entities, saved to GraphML")

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Re-extract all communes."""
    # Get all commune directories
    communes = sorted([
        d for d in DATA_PATH.iterdir()
        if d.is_dir() and d.name != "raw_data"
    ])

    print(f"\n🏛️  Grand Débat National - Entity Re-extraction")
    print(f"📋 Ontology: 22 entity types, 26 relationship types")
    print(f"📂 Found {len(communes)} communes to process")
    print(f"\n" + "="*60)

    for i, commune_path in enumerate(communes, 1):
        print(f"\n[{i}/{len(communes)}] Processing {commune_path.name}...")

        success = await re_extract_single_commune(commune_path)

        if success:
            processed_communes.append(commune_path.name)
        else:
            failed_communes.append(commune_path.name)

    # Summary
    print(f"\n{'='*60}")
    print(f"📊 EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"✅ Successful: {len(processed_communes)}")
    print(f"❌ Failed: {len(failed_communes)}")

    if failed_communes:
        print(f"\n⚠️  Failed communes:")
        for c in failed_communes:
            print(f"   - {c}")


if __name__ == "__main__":
    # Check for OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    print("🚀 Starting Grand Débat entity re-extraction...")
    asyncio.run(main())
