#!/usr/bin/env python3
"""
Extraction d'entités depuis les contributions Grand Débat Réunions Locales.
Réutilise l'infrastructure nano_graphrag existante.

Constitution Principe V : Interprétabilité de bout en bout
- Chaque contribution = un chunk unique
- Métadonnées préservées (ville, région, thèmes, participants)
- Provenance tracée via source_id
"""

import asyncio
import json
import re
import os
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import asdict

# Ajouter nano_graphrag au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from nano_graphrag.graphrag import GraphRAG
from nano_graphrag._llm import gpt_4o_mini_complete, openai_embedding
from nano_graphrag._op import extract_entities, generate_community_report
from nano_graphrag._utils import compute_mdhash_id, logger

# Configuration
SOURCE_FILE = "/Users/arthursarazin/Documents/sandbox/raw_delib/grand_debat_2019/Contributions_déposées_au_03_04_2019_Les_comptes-rendus_des_réunions_locales_du_site_Le_Grand_Débat.txt"
OUTPUT_DIR = Path("./law_data")

# Suivi
processed_depts = []
failed_depts = []


def parse_contributions(filepath: str) -> list[dict]:
    """
    Parse les contributions depuis le fichier source.

    Chaque contribution est délimitée par '--- Contribution N ---'
    et contient des métadonnées clé:valeur.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Découper par délimiteur de contribution
    parts = re.split(r'\n--- Contribution (\d+) ---\n', content)
    contributions = []

    # parts[0] est l'en-tête, puis alternance [numéro, contenu, numéro, contenu, ...]
    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break

        contrib_num = int(parts[i])
        contrib_content = parts[i + 1].strip()

        if not contrib_content:
            continue

        # Extraire les métadonnées
        metadata = {}
        for line in contrib_content.split('\n'):
            if ':' in line:
                key, _, value = line.partition(':')
                key = key.strip().lower().replace(' ', '_').replace("'", "_")
                metadata[key] = value.strip()

        # Récupérer le code département (avec padding si nécessaire)
        dept_code = metadata.get("code_département", "unknown")
        if dept_code.isdigit() and len(dept_code) < 2:
            dept_code = dept_code.zfill(2)  # "3" -> "03"

        contributions.append({
            "id": contrib_num,
            "content": contrib_content,
            "dept_code": dept_code,
            "ville": metadata.get("ville", ""),
            "region": metadata.get("région", ""),
            "themes": metadata.get("sur_quel_s_theme_s_votre_reunion_a_t_elle_porte", ""),
            "titre": metadata.get("titre", ""),
            "participants": metadata.get("combien_de_participants_etaient_presents", ""),
        })

    return contributions


async def traiter_departement(dept_code: str, contributions: list[dict]) -> bool:
    """
    Traite toutes les contributions d'un département.

    Crée un dossier GD_Reunions_{dept_code}/ avec :
    - kv_store_text_chunks.json : chunks des contributions
    - graph_chunk_entity_relation.graphml : entités extraites
    - kv_store_community_reports.json : rapports de communauté
    """
    target_dir = OUTPUT_DIR / f"GD_Reunions_{dept_code}"
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Traitement du département {dept_code}")
    print(f"  - {len(contributions)} contributions")
    print(f"  - Dossier: {target_dir}")
    print(f"{'='*60}")

    try:
        # Créer le dict de chunks (un par contribution)
        chunks = {}
        full_docs = {}

        for contrib in contributions:
            chunk_id = compute_mdhash_id(contrib["content"], prefix="contrib-")
            doc_id = f"GD_Reunions_{dept_code}"

            chunks[chunk_id] = {
                "tokens": len(contrib["content"].split()),  # Approximatif
                "content": contrib["content"],
                "chunk_order_index": contrib["id"],
                "full_doc_id": doc_id,
                # Métadonnées additionnelles pour provenance
                "source_contribution_id": contrib["id"],
                "source_ville": contrib["ville"],
                "source_themes": contrib["themes"],
            }

            # Document complet (si pas déjà créé)
            if doc_id not in full_docs:
                full_docs[doc_id] = {
                    "content": f"Réunions locales du Grand Débat National - Département {dept_code}"
                }

        # Sauvegarder les chunks
        with open(target_dir / "kv_store_text_chunks.json", 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        # Sauvegarder les documents complets
        with open(target_dir / "kv_store_full_docs.json", 'w', encoding='utf-8') as f:
            json.dump(full_docs, f, ensure_ascii=False, indent=2)

        print(f"  Chunks sauvegardés: {len(chunks)}")

        # Initialiser GraphRAG (réutilise l'infrastructure existante)
        rag = GraphRAG(
            working_dir=str(target_dir),
            best_model_func=gpt_4o_mini_complete,
            cheap_model_func=gpt_4o_mini_complete,
            embedding_func=openai_embedding,
        )

        print(f"  Extraction des entités avec ontologie Grand Débat...")

        # Extraire les entités
        maybe_new_kg = await extract_entities(
            chunks=chunks,
            knwoledge_graph_inst=rag.chunk_entity_relation_graph,
            entity_vdb=rag.entities_vdb,
            tokenizer_wrapper=rag.tokenizer_wrapper,
            global_config=asdict(rag),
            using_amazon_bedrock=False,
        )

        if maybe_new_kg is None:
            print(f"  Aucune entité extraite")
            return False

        rag.chunk_entity_relation_graph = maybe_new_kg

        # Générer les rapports de communauté
        print(f"  Génération des rapports de communauté...")
        await rag.chunk_entity_relation_graph.clustering(rag.graph_cluster_algorithm)
        await generate_community_report(
            rag.community_reports,
            rag.chunk_entity_relation_graph,
            rag.tokenizer_wrapper,
            asdict(rag)
        )

        # Sauvegarder tout
        print(f"  Sauvegarde sur disque...")
        await rag._insert_done()

        print(f"  Département {dept_code} traité avec succès")
        return True

    except Exception as e:
        print(f"  ERREUR département {dept_code}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """
    Point d'entrée principal.
    Parse toutes les contributions et les traite par département.
    """
    # Vérifier la clé API
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERREUR: Variable d'environnement OPENAI_API_KEY non définie")
        sys.exit(1)

    # Créer le dossier de sortie
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Parser les contributions
    print(f"\nGrand Débat National - Extraction d'entités")
    print(f"Source: {SOURCE_FILE}")
    print(f"{'='*60}")

    contributions = parse_contributions(SOURCE_FILE)
    print(f"\n{len(contributions)} contributions parsées")

    # Regrouper par département
    by_dept = defaultdict(list)
    for c in contributions:
        by_dept[c["dept_code"]].append(c)

    print(f"{len(by_dept)} départements trouvés")

    # Afficher la distribution
    print(f"\nDistribution par département:")
    for dept, contribs in sorted(by_dept.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"  {dept}: {len(contribs)} contributions")
    print(f"  ... et {len(by_dept) - 10} autres départements")

    # Traiter chaque département
    for i, (dept_code, dept_contribs) in enumerate(sorted(by_dept.items()), 1):
        print(f"\n[{i}/{len(by_dept)}] Département {dept_code}...")

        success = await traiter_departement(dept_code, dept_contribs)

        if success:
            processed_depts.append(dept_code)
        else:
            failed_depts.append(dept_code)

    # Résumé final
    print(f"\n{'='*60}")
    print(f"EXTRACTION TERMINÉE")
    print(f"{'='*60}")
    print(f"Réussis: {len(processed_depts)} départements")
    print(f"Échoués: {len(failed_depts)} départements")

    if failed_depts:
        print(f"\nDépartements en erreur:")
        for d in failed_depts:
            print(f"  - {d}")


if __name__ == "__main__":
    print("Grand Débat National - Pipeline d'extraction d'entités")
    print("Constitution Principe V : Interprétabilité de bout en bout")
    asyncio.run(main())
