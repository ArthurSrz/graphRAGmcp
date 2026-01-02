#!/usr/bin/env python3
"""
Migration script to add entity_name attribute to existing graph nodes.

The bug fix requires entity_name to be stored as a node attribute,
but existing GraphML files only have entity_name as the node ID.

This script:
1. Reads all GraphML files in the cache directories
2. Adds entity_name attribute to each node (using the node ID)
3. Saves the updated GraphML files

Usage:
    python migrate_add_entity_name.py [cache_directory]
"""

import os
import sys
import networkx as nx
from pathlib import Path


def migrate_graph(graphml_path: Path) -> bool:
    """Migrate a single GraphML file to add entity_name attribute."""
    try:
        print(f"Processing: {graphml_path}")

        # Load the graph
        G = nx.read_graphml(str(graphml_path))

        # Track changes
        updated_count = 0

        # Add entity_name attribute to each node
        for node_id in list(G.nodes()):
            node_data = G.nodes[node_id]

            # Only add if not already present
            if 'entity_name' not in node_data:
                G.nodes[node_id]['entity_name'] = node_id
                updated_count += 1

        if updated_count > 0:
            # Save the updated graph
            nx.write_graphml(G, str(graphml_path))
            print(f"  ✓ Updated {updated_count} nodes")
            return True
        else:
            print(f"  → Already migrated (all nodes have entity_name)")
            return False

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def find_and_migrate_graphs(base_dir: str = "."):
    """Find all GraphML files and migrate them."""
    base_path = Path(base_dir)

    # Find all .graphml files
    graphml_files = list(base_path.rglob("*.graphml"))

    if not graphml_files:
        print(f"No GraphML files found in {base_dir}")
        return

    print(f"Found {len(graphml_files)} GraphML files\n")

    migrated = 0
    skipped = 0
    failed = 0

    for graphml_file in graphml_files:
        result = migrate_graph(graphml_file)
        if result:
            migrated += 1
        elif result is False:
            skipped += 1
        else:
            failed += 1

    print(f"\n" + "="*60)
    print(f"Migration complete:")
    print(f"  Migrated: {migrated} files")
    print(f"  Skipped:  {skipped} files (already migrated)")
    print(f"  Failed:   {failed} files")
    print("="*60)


if __name__ == "__main__":
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    find_and_migrate_graphs(base_dir)
