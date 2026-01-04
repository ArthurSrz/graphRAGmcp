# Comparaison des résultats attendus : query_all vs surgical

## Test Query
**"Quelles sont les principales préoccupations des citoyens sur les transports ?"**

---

## 1️⃣ `grand_debat_query_all` - SANS chunks de texte

### Commande MCP
```bash
mcp call grand_debat_query_all '{
  "query": "Quelles sont les principales préoccupations des citoyens sur les transports ?",
  "mode": "global",
  "max_communes": 3
}'
```

### Structure de la réponse
```json
{
  "success": true,
  "query": "Quelles sont les principales préoccupations des citoyens sur les transports ?",
  "mode": "global",
  "communes_queried": 3,
  "communes_list": ["Andilly", "Angoulins", "Bernay_Saint_Martin"],
  "answer": "Les citoyens mentionnent les transports en commun et les taxes sur les carburants...",
  "provenance": {
    "entities": [
      {"name": "TRANSPORTS EN COMMUN", "commune": "Andilly"},
      {"name": "TAXES SUR CARBURANTS", "commune": "Angoulins"}
    ],
    "communities": [
      {"title": "Cluster L0C2_C0", "commune": "Andilly"}
    ],
    "source_quotes": []  // ❌ VIDE - Pas de chunks de texte !
  }
}
```

### Caractéristiques
- ❌ **Pas de chunks de texte** : `source_quotes` est vide
- ❌ **Entités sans description** : Seulement les noms
- ❌ **Communities génériques** : Titres de clusters sans détails
- ❌ **Réponse générique** : Pas de citations spécifiques
- ⏱️ **Rapide** : ~5-10 secondes
- 🔴 **Qualité** : Faible - Informations de 2ème niveau

---

## 2️⃣ `grand_debat_query_all_surgical` - AVEC chunks de texte

### Commande MCP
```bash
mcp call grand_debat_query_all_surgical '{
  "query": "Quelles sont les principales préoccupations des citoyens sur les transports ?",
  "max_communes": 3
}'
```

### Structure de la réponse
```json
{
  "success": true,
  "query": "Quelles sont les principales préoccupations des citoyens sur les transports ?",
  "architecture": "Parallel Surgical RAG (56 Mini-Worlds)",
  "mini_worlds_count": 3,
  "aggregated_answer": "À Andilly, les citoyens demandent...\n\n---\n\nÀ Angoulins, les contributions mentionnent...\n\n---\n\nÀ Bernay_Saint_Martin...",
  "aggregated_stats": {
    "total_communes_queried": 3,
    "successful_queries": 3,
    "total_entities": 150,
    "total_chunks": 45,  // ✅ CHUNKS RÉCUPÉRÉS !
    "total_relationships": 200,
    "avg_chunks_per_commune": 15.0
  },
  "mini_worlds": [
    {
      "commune": "Andilly",
      "entities": 50,
      "chunks": 15,  // ✅ 15 chunks de texte réels
      "relationships": 67
    },
    {
      "commune": "Angoulins",
      "entities": 55,
      "chunks": 18,  // ✅ 18 chunks de texte réels
      "relationships": 72
    },
    {
      "commune": "Bernay_Saint_Martin",
      "entities": 45,
      "chunks": 12,  // ✅ 12 chunks de texte réels
      "relationships": 61
    }
  ],
  "answers_sample": [
    "À Andilly, les citoyens demandent 'le développement des lignes de bus vers les zones rurales' et 'une réduction des taxes sur le carburant'. Les contributions mentionnent...",
    "À Angoulins, les préoccupations portent sur 'l'amélioration des pistes cyclables' et 'la gratuité des transports en commun pour les étudiants'...",
    "À Bernay_Saint_Martin, les citoyens réclament 'une meilleure desserte des hameaux' et 'la baisse des prix du carburant'..."
  ]
}
```

### Exemple de provenance (dans chaque mini-world)
```json
{
  "provenance": {
    "entities": [
      {
        "name": "TRANSPORTS EN COMMUN",
        "type": "THEME",
        "description": "Amélioration et développement des transports publics",
        "commune": "Andilly"
      }
    ],
    "relationships": [
      {
        "source": "TRANSPORTS EN COMMUN",
        "target": "ZONES RURALES",
        "description": "Demande de développement des lignes de bus",
        "weight": 0.95
      }
    ],
    "source_quotes": [  // ✅ CHUNKS DE TEXTE RÉELS !
      {
        "id": "chunk-a1b2c3",
        "content": "Il faut développer les lignes de bus vers les zones rurales car beaucoup de citoyens n'ont pas accès aux transports en commun. Les personnes âgées sont particulièrement touchées.",
        "commune": "Andilly"
      },
      {
        "id": "chunk-d4e5f6",
        "content": "Les taxes sur le carburant sont trop élevées. Baisser ces taxes permettrait aux familles modestes de se déplacer plus facilement.",
        "commune": "Andilly"
      }
    ]
  }
}
```

### Caractéristiques
- ✅ **45 chunks de texte** récupérés (15 par commune)
- ✅ **Citations exactes** : Contributions citoyennes réelles
- ✅ **Recherche vectorielle** : Chunks pertinents sélectionnés
- ✅ **Réponse détaillée** : Citations spécifiques avec sources
- ✅ **Provenance complète** : Entités + relations + chunks
- ⏱️ **Plus lent** : ~30-60 secondes (parallélisé)
- 🟢 **Qualité** : Excellente - Sources primaires

---

## 📊 Tableau comparatif

| Aspect | `query_all` | `surgical` |
|--------|-------------|------------|
| **Chunks de texte** | 0 ❌ | ~45 ✅ |
| **Source quotes** | Vide `[]` | Rempli avec vraies contributions |
| **Type de contenu** | Noms d'entités + summaries | Texte citoyen brut |
| **Recherche** | Filtrage keywords | Recherche vectorielle |
| **Qualité réponse** | Générique | Spécifique avec citations |
| **Longueur réponse** | ~500-1000 mots | ~2000-5000 mots |
| **Préservation info** | <10% 🔴 | 100% ✅ |
| **Temps exécution** | 5-10s | 30-60s |

---

## 🎯 Exemple concret de différence

### Query: "Que demandent les citoyens sur les transports ?"

#### Réponse `query_all` (sans chunks)
> "Les citoyens mentionnent les transports en commun, les taxes sur le carburant et les pistes cyclables. Plusieurs communes évoquent ces thématiques."

**Problème** : Aucune citation, aucun détail, information générique.

#### Réponse `surgical` (avec chunks)
> "**À Andilly**, les citoyens demandent explicitement :
> - 'le développement des lignes de bus vers les zones rurales car beaucoup de citoyens n'ont pas accès aux transports en commun' (Chunk-a1b2c3)
> - 'baisser les taxes sur le carburant pour permettre aux familles modestes de se déplacer' (Chunk-d4e5f6)
>
> **À Angoulins**, les contributions portent sur :
> - 'l'amélioration des pistes cyclables pour encourager les déplacements doux' (Chunk-g7h8i9)
> - 'la gratuité des transports en commun pour les étudiants et personnes âgées' (Chunk-j0k1l2)
>
> **À Bernay_Saint_Martin**, on trouve :
> - 'une meilleure desserte des hameaux isolés' (Chunk-m3n4o5)
> - 'la baisse des prix du carburant diesel' (Chunk-p6q7r8)"

**Avantage** : Citations précises, sources traçables, détails spécifiques par commune.

---

## 🧪 Comment tester

### 1. Démarrer le serveur MCP
```bash
cd /home/user/graphRAGmcp
python server.py
```

### 2. Dans un autre terminal, tester query_all
```bash
mcp call grand_debat_query_all '{
  "query": "Quelles sont les principales préoccupations des citoyens sur les transports ?",
  "mode": "global",
  "max_communes": 3
}'
```

### 3. Tester surgical
```bash
mcp call grand_debat_query_all_surgical '{
  "query": "Quelles sont les principales préoccupations des citoyens sur les transports ?",
  "max_communes": 3
}'
```

### 4. Comparer
- **Champs à vérifier** :
  - `provenance.source_quotes` : Vide dans query_all, rempli dans surgical
  - `aggregated_stats.total_chunks` : 0 dans query_all, ~45 dans surgical
  - Longueur et détail de `answer` / `aggregated_answer`
  - Présence de citations entre guillemets dans surgical

---

## 💡 Conclusion

**Pour préserver les réponses complètes et accéder aux vraies contributions citoyennes**, utilisez **`grand_debat_query_all_surgical`**.

La différence clé n'est **pas** le nombre de tokens, mais **la présence des chunks de texte** qui contiennent les contributions citoyennes réelles.
