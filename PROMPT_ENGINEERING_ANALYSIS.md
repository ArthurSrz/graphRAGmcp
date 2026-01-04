# Analyse du Prompt Engineering : query_all vs surgical

## 🎯 Différences de prompts et leur impact sur la préservation des réponses

### 1️⃣ `grand_debat_query_all` - Prompt court et synthétique

**Fichier** : `server.py:1564-1578`

```python
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

# Appel LLM
answer = await gpt_5_nano_complete(prompt, max_tokens=8192)
```

**Caractéristiques** :
- ⚠️ **"Synthétise"** : Encourage explicitement la compression
- ⚠️ **Pas de contrainte de longueur** : Limite implicite à 8192 tokens
- ⚠️ **Contexte limité** : ~1,936 tokens (sans chunks de texte)
- ✅ **En français** : Adapté au contenu

**Impact sur préservation** :
- 🔴 Le mot "synthétise" incite le LLM à **résumer** plutôt que préserver
- 🔴 Pas de guidance sur la structure attendue
- 🔴 Pas d'instruction explicite sur la longueur minimale

---

### 2️⃣ `grand_debat_surgical_query` - Prompt détaillé et prescriptif

**Fichier** : `server.py:1813-1880` (pour surgical query)

```python
prompt = f"""Tu es un analyste expert des données citoyennes du Grand Débat National.
Ton rôle est de fournir une analyse EXHAUSTIVE et PRÉCISE basée sur le graphe de connaissances reconstitué.

QUESTION: {query}

GRAPHE DE CONNAISSANCES RECONSTITUÉ ({len(final_commune_ids)} communes sur {total_communes_available} disponibles,
expansion multi-hop 5 niveaux):
{context}

ONTOLOGIE CIVIQUE DU GRAPHE:
Entités: PROPOSITION, THEMATIQUE, SERVICEPUBLIC, DOLEANCE, ACTEURINSTITUTIONNEL, OPINION, CITOYEN, CONCEPT,
REFORMEDEMOCRATIQUE, TERRITOIRE, COMMUNE, CONTRIBUTION
Relations: RELATED_TO, PROPOSE, FAIT_PARTIE_DE, CONCERNE, EXPRIME

[... suite du prompt ...]

RÈGLES ABSOLUES:
- Utilise OBLIGATOIREMENT les headers Markdown (# ##) pour structure forte
- Cite les entités EXACTEMENT comme dans le contexte avec leur type ontologique
- Chaque fait DOIT avoir sa commune source et son entité justificative
- Si info non disponible: "Non documenté dans les {len(final_commune_ids)} communes analysées"
- Réponds en français avec conviction chirurgicale

EXTRACTION CHIRURGICALE:"""

answer = await gpt_5_nano_complete(prompt, max_tokens=8192)
```

**Caractéristiques** :
- ✅ **"EXHAUSTIVE et PRÉCISE"** : Encourage la complétude
- ✅ **Règles absolues** : Contraintes strictes sur citations et sources
- ✅ **Structure imposée** : Headers Markdown obligatoires
- ✅ **Contexte riche** : Inclut chunks de texte (~200k tokens potentiel)

---

### 3️⃣ `grand_debat_query_all_surgical` (via rag.aquery) - Prompt nano-graphrag

**Fichier** : `server.py:2050-2056` + `nano_graphrag/prompt.py:396-433`

```python
# Appel avec response_type personnalisé
result = await rag.aquery(
    query,
    param=QueryParam(
        mode="local",
        return_provenance=include_sources,
        response_type="Comprehensive multi-commune analysis: 2500-5000 words total.
        Structure: Introduction (2-3 sentences) + ## Analyse par commune
        (one detailed paragraph per commune with provenance, 50-100 words each) +
        ## Synthèse transversale (patterns and variations across communes)"
    )
)
```

**Prompt système nano-graphrag** :
```
---Role---

You are a helpful assistant responding to questions about data in the tables provided.

---Goal---

Generate a response of the target length and format that responds to the user's question,
summarizing all information in the input data tables appropriate for the response length
and format, and incorporating any relevant general knowledge.

If you don't know the answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Target response length and format---

{response_type}  ← "Comprehensive multi-commune analysis: 2500-5000 words..."

---Data tables---

{context_data}  ← Inclut entities, relationships, communities, ET chunks de texte

---Goal---

Generate a response of the target length and format...
If you don't know the answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Target response length and format---

{response_type}

Add sections and commentary to the response as appropriate for the length and format.
Style the response in markdown.
```

**Caractéristiques** :
- ✅ **Longueur explicite** : "2500-5000 words total"
- ✅ **Structure détaillée** : Introduction + Analyse par commune + Synthèse
- ✅ **Provenance obligatoire** : "with provenance" dans response_type
- ✅ **Répété deux fois** : Le goal et response_type sont répétés pour insister
- ✅ **"Do not make anything up"** : Limite les hallucinations
- ✅ **Contexte complet** : Data tables incluent chunks de texte

---

## 📊 Comparaison des prompts

| Aspect | `query_all` | `surgical query` | `surgical via rag.aquery` |
|--------|-------------|------------------|---------------------------|
| **Mot-clé principal** | "Synthétise" ❌ | "EXHAUSTIVE" ✅ | "Comprehensive" ✅ |
| **Longueur guidée** | Non ❌ | Non | Oui "2500-5000 words" ✅ |
| **Structure imposée** | Non ❌ | Oui (headers Markdown) ✅ | Oui (détaillée) ✅ |
| **Citations obligatoires** | "Cite des exemples" ⚠️ | "DOIT avoir source" ✅ | "with provenance" ✅ |
| **Protection hallucinations** | "Reste factuel" ⚠️ | Oui ✅ | "Do not make anything up" ✅ |
| **Contexte disponible** | 1,936 tokens ❌ | ~10k tokens | ~200k tokens ✅ |
| **Chunks de texte** | Non ❌ | Oui ✅ | Oui ✅ |

---

## 🔍 Impact du mot "Synthétise"

### Prompt `query_all`
```
INSTRUCTIONS:
- Synthétise les informations de plusieurs communes  ← COMPRESSION ENCOURAGÉE
```

**Effet psychologique sur le LLM** :
- "Synthétiser" = **résumer**, **condenser**, **réduire**
- Le LLM va naturellement **supprimer les détails** pour faire tenir tout dans une réponse concise
- Contradictoire avec "Cite des exemples spécifiques"

### Prompt `surgical query`
```
Ton rôle est de fournir une analyse EXHAUSTIVE et PRÉCISE  ← COMPLÉTUDE ENCOURAGÉE
```

**Effet psychologique sur le LLM** :
- "EXHAUSTIVE" = **tout inclure**, **ne rien omettre**
- "PRÉCISE" = **détails exacts**, **citations textuelles**
- Renforce la préservation de l'information

### Prompt `rag.aquery`
```
Target response length: 2500-5000 words total  ← LONGUEUR MINIMALE IMPOSÉE
Structure: ... (one detailed paragraph per commune with provenance, 50-100 words each)
```

**Effet psychologique sur le LLM** :
- Longueur minimale **force** le LLM à développer
- Structure détaillée **garantit** qu'aucune commune n'est oubliée
- "with provenance" **oblige** les citations

---

## 💡 Recommandations de prompt engineering

### Pour améliorer `grand_debat_query_all`

Si vous voulez garder l'architecture à un seul LLM call, modifiez le prompt :

```python
prompt = f"""Tu es un analyste expert des contributions citoyennes du Grand Débat National 2019.
Ton rôle est de fournir une ANALYSE EXHAUSTIVE ET DÉTAILLÉE des {len(communes_loaded)} communes de Charente-Maritime.

QUESTION: {query}

CONTEXTE DU GRAPHE DE CONNAISSANCES:
{context}

INSTRUCTIONS IMPÉRATIVES:
- Produis une réponse de 3000-5000 mots minimum
- Structure OBLIGATOIRE:
  * Introduction (2-3 phrases)
  * ## Analyse détaillée par commune (un paragraphe de 100-150 mots PAR commune)
  * ## Synthèse transversale (patterns communs et variations)
- Chaque fait DOIT inclure:
  * Citation textuelle entre guillemets
  * Source: [Nom commune]
  * Type d'entité si disponible
- NE RÉSUME PAS : Préserve tous les détails importants
- Si information manquante: indique clairement "Non documenté"
- Réponds en français avec précision chirurgicale

ANALYSE EXHAUSTIVE:"""
```

**Changements clés** :
1. ❌ **Retire** "Synthétise"
2. ✅ **Ajoute** "EXHAUSTIVE ET DÉTAILLÉE"
3. ✅ **Impose** longueur minimale "3000-5000 mots"
4. ✅ **Structure** obligatoire par commune
5. ✅ **"NE RÉSUME PAS"** : Instruction explicite anti-compression
6. ✅ **Citations obligatoires**

### Mais le vrai problème reste...

**Même avec un meilleur prompt**, `query_all` souffre de :
- ❌ **Pas de chunks de texte** : Le contexte n'a que des noms d'entités
- ❌ **Contexte limité** : ~1,936 tokens vs ~200k dans surgical
- ❌ **Un seul appel LLM** : Doit tout compresser dans 8192 tokens

**Le prompt ne peut pas compenser l'absence de données sources !**

---

## 🎯 Conclusion sur le prompt engineering

| Problème | Impact | Solution |
|----------|--------|----------|
| Mot "Synthétise" | Encourage compression | ❌ Changer en "EXHAUSTIVE" |
| Pas de longueur min | LLM peut être bref | ❌ Imposer "3000-5000 mots" |
| Pas de structure | Communes oubliées | ❌ Structure par commune |
| **Pas de chunks** 🔴 | **Données manquantes** | ✅ **Utiliser surgical** |

**Le prompt engineering peut améliorer marginalement, mais ne résout pas le problème fondamental : l'absence de chunks de texte dans query_all.**

---

## 📈 Tests proposés

### Test A : Modifier uniquement le prompt de query_all
Sans changer l'architecture, améliorer le prompt pour voir si ça aide.

**Attendu** : Légère amélioration, mais toujours <20% de préservation car contexte limité.

### Test B : Comparer surgical avec différents response_type
Tester l'impact de la longueur guidée :

```python
# Version courte
response_type="Brief summary: 500 words"

# Version longue
response_type="Comprehensive analysis: 5000 words"
```

**Attendu** : La version longue préserve plus d'information.

### Test C : Mesurer l'impact de "Synthétise" vs "EXHAUSTIVE"
Deux versions de query_all identiques sauf le mot-clé.

**Attendu** : "EXHAUSTIVE" produit des réponses ~30% plus longues.

---

## 🔬 Méthodologie d'évaluation

Pour mesurer l'impact du prompt engineering :

1. **Compter les citations** : Nombre de citations textuelles entre guillemets
2. **Longueur de réponse** : Nombre de mots
3. **Communes mentionnées** : Nombre de communes citées explicitement
4. **Détails préservés** : Présence de chiffres, noms spécifiques, dates

**Exemple de métrique** :
```python
def evaluate_response(response):
    return {
        'word_count': len(response.split()),
        'citation_count': response.count('"'),
        'commune_mentions': len(set(re.findall(r'\[([\w\s]+)\]', response))),
        'specificity_score': len(re.findall(r'\d+|[A-Z][a-zé]+\s[A-Z][a-zé]+', response))
    }
```

---

## ✅ Recommandation finale

**Le prompt engineering seul ne suffit pas.**

Pour une préservation optimale des réponses :
1. ✅ Utilisez `grand_debat_query_all_surgical` (chunks + bon prompt)
2. ⚠️ Si vous devez utiliser `query_all`, améliorez le prompt ET ajoutez la récupération des chunks
3. ❌ Ne comptez pas uniquement sur le prompt pour compenser l'absence de données

**La combinaison gagnante** : `Chunks de texte + Prompt exhaustif + Longueur guidée`
