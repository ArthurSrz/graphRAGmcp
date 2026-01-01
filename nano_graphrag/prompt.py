"""
Reference:
 - Prompts are from [graphrag](https://github.com/microsoft/graphrag)
"""

GRAPH_FIELD_SEP = "<SEP>"
PROMPTS = {}

PROMPTS[
    "claim_extraction"
] = """-Target activity-
You are an intelligent assistant that helps a human analyst to analyze claims against certain entities presented in a text document.

-Goal-
Given a text document that is potentially relevant to this activity, an entity specification, and a claim description, extract all entities that match the entity specification and all claims against those entities.

-Steps-
1. Extract all named entities that match the predefined entity specification. Entity specification can either be a list of entity names or a list of entity types.
2. For each entity identified in step 1, extract all claims associated with the entity. Claims need to match the specified claim description, and the entity should be the subject of the claim.
For each claim, extract the following information:
- Subject: name of the entity that is subject of the claim, capitalized. The subject entity is one that committed the action described in the claim. Subject needs to be one of the named entities identified in step 1.
- Object: name of the entity that is object of the claim, capitalized. The object entity is one that either reports/handles or is affected by the action described in the claim. If object entity is unknown, use **NONE**.
- Claim Type: overall category of the claim, capitalized. Name it in a way that can be repeated across multiple text inputs, so that similar claims share the same claim type
- Claim Status: **TRUE**, **FALSE**, or **SUSPECTED**. TRUE means the claim is confirmed, FALSE means the claim is found to be False, SUSPECTED means the claim is not verified.
- Claim Description: Detailed description explaining the reasoning behind the claim, together with all the related evidence and references.
- Claim Date: Period (start_date, end_date) when the claim was made. Both start_date and end_date should be in ISO-8601 format. If the claim was made on a single date rather than a date range, set the same date for both start_date and end_date. If date is unknown, return **NONE**.
- Claim Source Text: List of **all** quotes from the original text that are relevant to the claim.

Format each claim as (<subject_entity>{tuple_delimiter}<object_entity>{tuple_delimiter}<claim_type>{tuple_delimiter}<claim_status>{tuple_delimiter}<claim_start_date>{tuple_delimiter}<claim_end_date>{tuple_delimiter}<claim_description>{tuple_delimiter}<claim_source>)

3. Return output in English as a single list of all the claims identified in steps 1 and 2. Use **{record_delimiter}** as the list delimiter.

4. When finished, output {completion_delimiter}

-Examples-
Example 1:
Entity specification: organization
Claim description: red flags associated with an entity
Text: According to an article on 2022/01/10, Company A was fined for bid rigging while participating in multiple public tenders published by Government Agency B. The company is owned by Person C who was suspected of engaging in corruption activities in 2015.
Output:

(COMPANY A{tuple_delimiter}GOVERNMENT AGENCY B{tuple_delimiter}ANTI-COMPETITIVE PRACTICES{tuple_delimiter}TRUE{tuple_delimiter}2022-01-10T00:00:00{tuple_delimiter}2022-01-10T00:00:00{tuple_delimiter}Company A was found to engage in anti-competitive practices because it was fined for bid rigging in multiple public tenders published by Government Agency B according to an article published on 2022/01/10{tuple_delimiter}According to an article published on 2022/01/10, Company A was fined for bid rigging while participating in multiple public tenders published by Government Agency B.)
{completion_delimiter}

Example 2:
Entity specification: Company A, Person C
Claim description: red flags associated with an entity
Text: According to an article on 2022/01/10, Company A was fined for bid rigging while participating in multiple public tenders published by Government Agency B. The company is owned by Person C who was suspected of engaging in corruption activities in 2015.
Output:

(COMPANY A{tuple_delimiter}GOVERNMENT AGENCY B{tuple_delimiter}ANTI-COMPETITIVE PRACTICES{tuple_delimiter}TRUE{tuple_delimiter}2022-01-10T00:00:00{tuple_delimiter}2022-01-10T00:00:00{tuple_delimiter}Company A was found to engage in anti-competitive practices because it was fined for bid rigging in multiple public tenders published by Government Agency B according to an article published on 2022/01/10{tuple_delimiter}According to an article published on 2022/01/10, Company A was fined for bid rigging while participating in multiple public tenders published by Government Agency B.)
{record_delimiter}
(PERSON C{tuple_delimiter}NONE{tuple_delimiter}CORRUPTION{tuple_delimiter}SUSPECTED{tuple_delimiter}2015-01-01T00:00:00{tuple_delimiter}2015-12-30T00:00:00{tuple_delimiter}Person C was suspected of engaging in corruption activities in 2015{tuple_delimiter}The company is owned by Person C who was suspected of engaging in corruption activities in 2015)
{completion_delimiter}

-Real Data-
Use the following input for your answer.
Entity specification: {entity_specs}
Claim description: {claim_description}
Text: {input_text}
Output: """

PROMPTS[
    "community_report"
] = """You are an AI assistant that helps a human analyst to perform general information discovery. 
Information discovery is the process of identifying and assessing relevant information associated with certain entities (e.g., organizations and individuals) within a network.

# Goal
Write a comprehensive report of a community, given a list of entities that belong to the community as well as their relationships and optional associated claims. The report will be used to inform decision-makers about information associated with the community and their potential impact. The content of this report includes an overview of the community's key entities, their legal compliance, technical capabilities, reputation, and noteworthy claims.

# Report Structure

The report should include the following sections:

- TITLE: community's name that represents its key entities - title should be short but specific. When possible, include representative named entities in the title.
- SUMMARY: An executive summary of the community's overall structure, how its entities are related to each other, and significant information associated with its entities.
- IMPACT SEVERITY RATING: a float score between 0-10 that represents the severity of IMPACT posed by entities within the community.  IMPACT is the scored importance of a community.
- RATING EXPLANATION: Give a single sentence explanation of the IMPACT severity rating.
- DETAILED FINDINGS: A list of 5-10 key insights about the community. Each insight should have a short summary followed by multiple paragraphs of explanatory text grounded according to the grounding rules below. Be comprehensive.

Return output as a well-formed JSON-formatted string with the following format:
    {{
        "title": <report_title>,
        "summary": <executive_summary>,
        "rating": <impact_severity_rating>,
        "rating_explanation": <rating_explanation>,
        "findings": [
            {{
                "summary":<insight_1_summary>,
                "explanation": <insight_1_explanation>
            }},
            {{
                "summary":<insight_2_summary>,
                "explanation": <insight_2_explanation>
            }}
            ...
        ]
    }}

# Grounding Rules
Do not include information where the supporting evidence for it is not provided.


# Example Input
-----------
Text:
```
Entities:
```csv
id,entity,type,description
5,VERDANT OASIS PLAZA,geo,Verdant Oasis Plaza is the location of the Unity March
6,HARMONY ASSEMBLY,organization,Harmony Assembly is an organization that is holding a march at Verdant Oasis Plaza
```
Relationships:
```csv
id,source,target,description
37,VERDANT OASIS PLAZA,UNITY MARCH,Verdant Oasis Plaza is the location of the Unity March
38,VERDANT OASIS PLAZA,HARMONY ASSEMBLY,Harmony Assembly is holding a march at Verdant Oasis Plaza
39,VERDANT OASIS PLAZA,UNITY MARCH,The Unity March is taking place at Verdant Oasis Plaza
40,VERDANT OASIS PLAZA,TRIBUNE SPOTLIGHT,Tribune Spotlight is reporting on the Unity march taking place at Verdant Oasis Plaza
41,VERDANT OASIS PLAZA,BAILEY ASADI,Bailey Asadi is speaking at Verdant Oasis Plaza about the march
43,HARMONY ASSEMBLY,UNITY MARCH,Harmony Assembly is organizing the Unity March
```
```
Output:
{{
    "title": "Verdant Oasis Plaza and Unity March",
    "summary": "The community revolves around the Verdant Oasis Plaza, which is the location of the Unity March. The plaza has relationships with the Harmony Assembly, Unity March, and Tribune Spotlight, all of which are associated with the march event.",
    "rating": 5.0,
    "rating_explanation": "The impact severity rating is moderate due to the potential for unrest or conflict during the Unity March.",
    "findings": [
        {{
            "summary": "Verdant Oasis Plaza as the central location",
            "explanation": "Verdant Oasis Plaza is the central entity in this community, serving as the location for the Unity March. This plaza is the common link between all other entities, suggesting its significance in the community. The plaza's association with the march could potentially lead to issues such as public disorder or conflict, depending on the nature of the march and the reactions it provokes."
        }},
        {{
            "summary": "Harmony Assembly's role in the community",
            "explanation": "Harmony Assembly is another key entity in this community, being the organizer of the march at Verdant Oasis Plaza. The nature of Harmony Assembly and its march could be a potential source of threat, depending on their objectives and the reactions they provoke. The relationship between Harmony Assembly and the plaza is crucial in understanding the dynamics of this community."
        }},
        {{
            "summary": "Unity March as a significant event",
            "explanation": "The Unity March is a significant event taking place at Verdant Oasis Plaza. This event is a key factor in the community's dynamics and could be a potential source of threat, depending on the nature of the march and the reactions it provokes. The relationship between the march and the plaza is crucial in understanding the dynamics of this community."
        }},
        {{
            "summary": "Role of Tribune Spotlight",
            "explanation": "Tribune Spotlight is reporting on the Unity March taking place in Verdant Oasis Plaza. This suggests that the event has attracted media attention, which could amplify its impact on the community. The role of Tribune Spotlight could be significant in shaping public perception of the event and the entities involved."
        }}
    ]
}}


# Real Data

Use the following text for your answer. Do not make anything up in your answer.

Text:
```
{input_text}
```

The report should include the following sections:

- TITLE: community's name that represents its key entities - title should be short but specific. When possible, include representative named entities in the title.
- SUMMARY: An executive summary of the community's overall structure, how its entities are related to each other, and significant information associated with its entities.
- IMPACT SEVERITY RATING: a float score between 0-10 that represents the severity of IMPACT posed by entities within the community.  IMPACT is the scored importance of a community.
- RATING EXPLANATION: Give a single sentence explanation of the IMPACT severity rating.
- DETAILED FINDINGS: A list of 5-10 key insights about the community. Each insight should have a short summary followed by multiple paragraphs of explanatory text grounded according to the grounding rules below. Be comprehensive.

Return output as a well-formed JSON-formatted string with the following format:
    {{
        "title": <report_title>,
        "summary": <executive_summary>,
        "rating": <impact_severity_rating>,
        "rating_explanation": <rating_explanation>,
        "findings": [
            {{
                "summary":<insight_1_summary>,
                "explanation": <insight_1_explanation>
            }},
            {{
                "summary":<insight_2_summary>,
                "explanation": <insight_2_explanation>
            }}
            ...
        ]
    }}

# Grounding Rules
Do not include information where the supporting evidence for it is not provided.

Output:
"""

PROMPTS[
    "entity_extraction"
] = """-Objectif-
À partir d'un texte issu du Grand Débat National (consultation citoyenne française 2019), identifier toutes les entités civiques et leurs relations selon l'ontologie du Grand Débat.

-Contexte-
Ceci est une contribution citoyenne (compte-rendu de réunion locale) d'une commune française. Extraire les entités et relations qui capturent :
- Ce que les citoyens expriment (opinions, doléances, propositions)
- Quels thèmes et services publics sont concernés
- Quelles institutions et réformes sont mentionnées
- Les relations sémantiques entre ces éléments

-Étapes-
1. Identifier toutes les entités. Pour chaque entité identifiée, extraire les informations suivantes :
- entity_name: Nom de l'entité, en majuscules (en français)
- entity_type: Un des types suivants : [{entity_types}]
- entity_description: Description complète des attributs et activités de l'entité (en français)
Formater chaque entité ainsi : ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>

2. À partir des entités identifiées à l'étape 1, identifier toutes les paires (entité_source, entité_cible) qui sont *clairement liées* entre elles.
Pour chaque paire d'entités liées, extraire les informations suivantes :
- source_entity: nom de l'entité source, tel qu'identifié à l'étape 1
- target_entity: nom de l'entité cible, tel qu'identifié à l'étape 1
- relationship_type: **OBLIGATOIRE** - Utiliser UNIQUEMENT un des types suivants : [{relationship_types}]. NE PAS inventer de nouveaux types. Si aucun type ne correspond exactement, utiliser le type sémantiquement le plus proche de la liste.
- relationship_description: explication de pourquoi l'entité source et l'entité cible sont liées
- relationship_strength: score numérique indiquant la force de la relation entre les entités
Formater chaque relation ainsi : ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_type>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_strength>)

3. Retourner le résultat en français sous forme d'une liste unique de toutes les entités et relations identifiées. Utiliser **{record_delimiter}** comme délimiteur.

4. Une fois terminé, afficher {completion_delimiter}

######################
-Exemples Grand Débat National-
######################
Exemple 1 - Contribution citoyenne sur les services publics:

Entity_types: [Citoyen, Contribution, Thematique, Opinion, Doleance, ServicePublic, Proposition]
Text:
Jean-Pierre de Rochefort-sur-Mer a participé au Grand Débat le 15 février 2019. Dans sa contribution, il exprime son mécontentement concernant la fermeture des bureaux de poste ruraux. Il propose de maintenir une présence postale minimale dans chaque commune de moins de 2000 habitants. Il souligne également que les services publics sont essentiels pour maintenir le lien social dans les territoires ruraux.
################
Output:
("entity"{tuple_delimiter}"JEAN-PIERRE"{tuple_delimiter}"Citoyen"{tuple_delimiter}"Jean-Pierre est un citoyen de Rochefort-sur-Mer qui a participé au Grand Débat National le 15 février 2019."){record_delimiter}
("entity"{tuple_delimiter}"CONTRIBUTION JEAN-PIERRE"{tuple_delimiter}"Contribution"{tuple_delimiter}"Contribution citoyenne du 15 février 2019 concernant les services publics ruraux et la présence postale."){record_delimiter}
("entity"{tuple_delimiter}"SERVICES PUBLICS"{tuple_delimiter}"Thematique"{tuple_delimiter}"Thème du Grand Débat concernant l'organisation et l'accessibilité des services publics."){record_delimiter}
("entity"{tuple_delimiter}"MECONTENTEMENT FERMETURE POSTE"{tuple_delimiter}"Opinion"{tuple_delimiter}"Opinion négative exprimée sur la fermeture des bureaux de poste en zone rurale."){record_delimiter}
("entity"{tuple_delimiter}"FERMETURE BUREAUX POSTE RURAUX"{tuple_delimiter}"Doleance"{tuple_delimiter}"Doléance concernant la disparition des services postaux dans les petites communes."){record_delimiter}
("entity"{tuple_delimiter}"LA POSTE"{tuple_delimiter}"ServicePublic"{tuple_delimiter}"Service public postal mentionné dans la contribution."){record_delimiter}
("entity"{tuple_delimiter}"MAINTIEN PRESENCE POSTALE"{tuple_delimiter}"Proposition"{tuple_delimiter}"Proposition de maintenir une présence postale minimale dans les communes de moins de 2000 habitants."){record_delimiter}
("relationship"{tuple_delimiter}"JEAN-PIERRE"{tuple_delimiter}"CONTRIBUTION JEAN-PIERRE"{tuple_delimiter}"SOUMET"{tuple_delimiter}"Jean-Pierre soumet sa contribution au Grand Débat National."{tuple_delimiter}10){record_delimiter}
("relationship"{tuple_delimiter}"CONTRIBUTION JEAN-PIERRE"{tuple_delimiter}"SERVICES PUBLICS"{tuple_delimiter}"APPARTIENT_A"{tuple_delimiter}"La contribution appartient au thème des services publics."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"CONTRIBUTION JEAN-PIERRE"{tuple_delimiter}"MECONTENTEMENT FERMETURE POSTE"{tuple_delimiter}"EXPRIME"{tuple_delimiter}"La contribution exprime une opinion sur les fermetures de bureaux de poste."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"CONTRIBUTION JEAN-PIERRE"{tuple_delimiter}"FERMETURE BUREAUX POSTE RURAUX"{tuple_delimiter}"FAIT_REMONTER"{tuple_delimiter}"La contribution fait remonter cette doléance sur les fermetures."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"CONTRIBUTION JEAN-PIERRE"{tuple_delimiter}"MAINTIEN PRESENCE POSTALE"{tuple_delimiter}"FORMULE"{tuple_delimiter}"La contribution formule cette proposition de maintien postal."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"FERMETURE BUREAUX POSTE RURAUX"{tuple_delimiter}"LA POSTE"{tuple_delimiter}"CONCERNE"{tuple_delimiter}"La doléance concerne le service public postal La Poste."{tuple_delimiter}10){completion_delimiter}
#############################
Exemple 2 - Réunion citoyenne sur la démocratie:

Entity_types: [Contribution, Consultation, ReformeDemocratique, ModeScrutin, Consensus, Opinion, Thematique]
Text:
Les citoyens réunis à La Rochelle dans le cadre du Grand Débat National ont largement plébiscité l'introduction du référendum d'initiative citoyenne. Un consensus s'est dégagé sur la nécessité de réformer le mode de scrutin pour les élections législatives. La thématique de la démocratie et citoyenneté a suscité des débats animés.
#############
Output:
("entity"{tuple_delimiter}"REUNION LA ROCHELLE"{tuple_delimiter}"Contribution"{tuple_delimiter}"Contribution collective issue de la réunion citoyenne de La Rochelle dans le cadre du Grand Débat."){record_delimiter}
("entity"{tuple_delimiter}"GRAND DEBAT NATIONAL"{tuple_delimiter}"Consultation"{tuple_delimiter}"Consultation citoyenne nationale organisée en 2019 pour recueillir les avis des Français."){record_delimiter}
("entity"{tuple_delimiter}"REFERENDUM INITIATIVE CITOYENNE"{tuple_delimiter}"ReformeDemocratique"{tuple_delimiter}"Réforme démocratique visant à permettre aux citoyens d'initier des référendums."){record_delimiter}
("entity"{tuple_delimiter}"SCRUTIN LEGISLATIVES"{tuple_delimiter}"ModeScrutin"{tuple_delimiter}"Mode de scrutin actuel pour les élections législatives, jugé à réformer."){record_delimiter}
("entity"{tuple_delimiter}"CONSENSUS REFORME SCRUTIN"{tuple_delimiter}"Consensus"{tuple_delimiter}"Consensus dégagé sur la nécessité de réformer le mode de scrutin."){record_delimiter}
("entity"{tuple_delimiter}"SOUTIEN RIC"{tuple_delimiter}"Opinion"{tuple_delimiter}"Opinion favorable au référendum d'initiative citoyenne exprimée par les participants."){record_delimiter}
("entity"{tuple_delimiter}"DEMOCRATIE ET CITOYENNETE"{tuple_delimiter}"Thematique"{tuple_delimiter}"Thème du Grand Débat concernant la vie démocratique et la participation citoyenne."){record_delimiter}
("relationship"{tuple_delimiter}"REUNION LA ROCHELLE"{tuple_delimiter}"GRAND DEBAT NATIONAL"{tuple_delimiter}"FAIT_PARTIE_DE"{tuple_delimiter}"La réunion de La Rochelle fait partie du Grand Débat National."{tuple_delimiter}10){record_delimiter}
("relationship"{tuple_delimiter}"REUNION LA ROCHELLE"{tuple_delimiter}"SOUTIEN RIC"{tuple_delimiter}"EXPRIME"{tuple_delimiter}"La réunion exprime un soutien au RIC."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"REUNION LA ROCHELLE"{tuple_delimiter}"DEMOCRATIE ET CITOYENNETE"{tuple_delimiter}"APPARTIENT_A"{tuple_delimiter}"La réunion appartient au thème démocratie et citoyenneté."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"SOUTIEN RIC"{tuple_delimiter}"CONSENSUS REFORME SCRUTIN"{tuple_delimiter}"CONTRIBUE_A"{tuple_delimiter}"L'opinion favorable au RIC contribue au consensus sur la réforme."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"GRAND DEBAT NATIONAL"{tuple_delimiter}"CONSENSUS REFORME SCRUTIN"{tuple_delimiter}"REVELE"{tuple_delimiter}"Le Grand Débat révèle ce consensus sur la réforme du scrutin."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"REFERENDUM INITIATIVE CITOYENNE"{tuple_delimiter}"SCRUTIN LEGISLATIVES"{tuple_delimiter}"PROPOSE"{tuple_delimiter}"La réforme RIC propose de modifier le mode de scrutin."{tuple_delimiter}7){completion_delimiter}
#############################
-Real Data-
######################
Entity_types: {entity_types}
Text: {input_text}
######################
Output:
"""


PROMPTS[
    "summarize_entity_descriptions"
] = """Vous êtes un assistant chargé de générer un résumé complet des données fournies ci-dessous.
Étant donné une ou deux entités et une liste de descriptions, toutes liées à la même entité ou groupe d'entités.
Veuillez concaténer tout cela en une seule description complète. Assurez-vous d'inclure les informations de toutes les descriptions.
Si les descriptions fournies sont contradictoires, résolvez les contradictions et fournissez un résumé unique et cohérent.
Assurez-vous que le texte est écrit à la troisième personne et incluez les noms des entités pour le contexte.

#######
-Données-
Entités: {entity_name}
Liste des descriptions: {description_list}
#######
Résultat:
"""


PROMPTS[
    "entiti_continue_extraction"
] = """PLUSIEURS entités ont été manquées lors de la dernière extraction. Ajoutez-les ci-dessous en utilisant le même format :
"""

PROMPTS[
    "entiti_if_loop_extraction"
] = """Il semble que certaines entités aient encore été manquées. Répondez OUI | NON s'il reste des entités à ajouter.
"""

# ============================================================
# Grand Débat National - Ontologie Civique (depuis law_graph_core)
# Principe de la Constitution V : Interprétabilité de bout en bout
# ============================================================

PROMPTS["DEFAULT_ENTITY_TYPES"] = [
    # Participants principaux
    "Citoyen",           # Participant avec citoyenId, codePostal, dateParticipation
    "Contribution",      # Texte citoyen avec contributionId, texte, dateCreation
    "Consultation",      # Le Grand Débat avec dateDebut, dateFin, nombreParticipants

    # Questions & Thèmes
    "Question",          # Questions avec libelle, ordre, typeQuestion
    "Thematique",        # Thèmes majeurs avec nom, description

    # Traitement IA
    "ClusterSemantique", # Clusters sémantiques avec label, taille, centroide
    "Encodage",          # Embeddings vectoriels avec vecteur, modele, dimension
    "TypeRepondant",     # Type de répondant avec nom, pourcentage, description

    # Contenu extrait
    "Opinion",           # Opinion exprimée avec position, sujet, intensite
    "Proposition",       # Proposition avec titre, description, categorie
    "Doleance",          # Doléance avec objet, gravite, frequence
    "Verbatim",          # Citation directe avec texte, estTypique, scoreRepresentativite

    # Réformes
    "ReformeDemocratique",  # Réforme démocratique avec nom, nombreMentions
    "ReformeFiscale",       # Réforme fiscale avec nom, impact

    # Confiance & Institutions
    "NiveauConfiance",       # Niveau de confiance avec valeur, intensite
    "ActeurInstitutionnel",  # Acteur institutionnel avec nom, type, niveauConfiance
    "ServicePublic",         # Service public avec nom, domaine, priorite

    # Autres entités
    "Consensus",          # Points de consensus avec sujet, type, pourcentageAccord
    "CourantIdeologique", # Courant idéologique avec nom, pourcentage
    "CourantLaique",      # Courant laïque avec positionLoi1905
    "Territoire",         # Territoire géographique avec nom, type, population
    "TypeImpot",          # Type d'impôt avec nom, categorie, sentimentMoyen
    "ModeScrutin",        # Mode de scrutin avec nom, nombreMentions
    "MesureEcologique",   # Mesure écologique avec domaine, consensusObjectif
]

PROMPTS["DEFAULT_RELATIONSHIP_TYPES"] = [
    # Flux principal (Citoyen → Contribution → Question → Thème)
    "SOUMET",           # Citoyen SOUMET contribution
    "REPOND_A",         # Contribution RÉPOND À question
    "APPARTIENT_A",     # Question APPARTIENT À thème
    "FAIT_PARTIE_DE",   # Thème FAIT PARTIE DE consultation

    # Classification
    "CLASSE_DANS",      # Citoyen CLASSÉ DANS type de répondant
    "RESIDE_DANS",      # Citoyen RÉSIDE DANS territoire
    "REGROUPEE_DANS",   # Contribution REGROUPÉE DANS cluster sémantique
    "PRIORISE",         # Type de répondant PRIORISE thème

    # Extraction de contenu
    "EXPRIME",          # Contribution EXPRIME opinion
    "FORMULE",          # Contribution FORMULE proposition
    "FAIT_REMONTER",    # Contribution FAIT REMONTER doléance
    "CONTIENT",         # Contribution CONTIENT verbatim
    "TRADUIT",          # Contribution TRADUIT niveau de confiance
    "REPRESENTE",       # Verbatim REPRÉSENTE type de répondant

    # Spécialisation des réformes
    "EST_TYPE_DE",      # Réforme EST TYPE DE proposition
    "PROPOSE",          # Réforme démocratique PROPOSE mode de scrutin
    "PORTE_SUR_IMPOT",  # Réforme fiscale PORTE SUR type d'impôt

    # Confiance & Services
    "CIBLE",            # Niveau de confiance CIBLE acteur institutionnel
    "GERE",             # Acteur institutionnel GÈRE service public
    "CONCERNE",         # Doléance CONCERNE service public
    "FINANCE",          # Type d'impôt FINANCE service public

    # Consensus & Idéologie
    "SINSCRIT_DANS",    # Opinion S'INSCRIT DANS courant idéologique
    "CONTRIBUE_A",      # Opinion CONTRIBUE À consensus
    "REVELE",           # Consultation RÉVÈLE consensus
    "INCLUT",           # Thème INCLUT mesure écologique
    "PORTE_SUR_MESURE", # Consensus PORTE SUR mesure écologique
]

PROMPTS["DEFAULT_TUPLE_DELIMITER"] = "<|>"
PROMPTS["DEFAULT_RECORD_DELIMITER"] = "##"
PROMPTS["DEFAULT_COMPLETION_DELIMITER"] = "<|COMPLETE|>"

PROMPTS[
    "local_rag_response"
] = """---Role---

You are a helpful assistant responding to questions about data in the tables provided.


---Goal---

Generate a response of the target length and format that responds to the user's question, summarizing all information in the input data tables appropriate for the response length and format, and incorporating any relevant general knowledge.
If you don't know the answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Target response length and format---

{response_type}


---Data tables---

{context_data}


---Goal---

Generate a response of the target length and format that responds to the user's question, summarizing all information in the input data tables appropriate for the response length and format, and incorporating any relevant general knowledge.

If you don't know the answer, just say so. Do not make anything up.

Do not include information where the supporting evidence for it is not provided.


---Target response length and format---

{response_type}

Add sections and commentary to the response as appropriate for the length and format. Style the response in markdown.
"""

PROMPTS[
    "global_map_rag_points"
] = """---Role---

You are a helpful assistant responding to questions about data in the tables provided.


---Goal---

Generate a response consisting of a list of key points that responds to the user's question, summarizing all relevant information in the input data tables.

You should use the data provided in the data tables below as the primary context for generating the response.
If you don't know the answer or if the input data tables do not contain sufficient information to provide an answer, just say so. Do not make anything up.

Each key point in the response should have the following element:
- Description: A comprehensive description of the point.
- Importance Score: An integer score between 0-100 that indicates how important the point is in answering the user's question. An 'I don't know' type of response should have a score of 0.

The response should be JSON formatted as follows:
{{
    "points": [
        {{"description": "Description of point 1...", "score": score_value}},
        {{"description": "Description of point 2...", "score": score_value}}
    ]
}}

The response shall preserve the original meaning and use of modal verbs such as "shall", "may" or "will".
Do not include information where the supporting evidence for it is not provided.


---Data tables---

{context_data}

---Goal---

Generate a response consisting of a list of key points that responds to the user's question, summarizing all relevant information in the input data tables.

You should use the data provided in the data tables below as the primary context for generating the response.
If you don't know the answer or if the input data tables do not contain sufficient information to provide an answer, just say so. Do not make anything up.

Each key point in the response should have the following element:
- Description: A comprehensive description of the point.
- Importance Score: An integer score between 0-100 that indicates how important the point is in answering the user's question. An 'I don't know' type of response should have a score of 0.

The response shall preserve the original meaning and use of modal verbs such as "shall", "may" or "will".
Do not include information where the supporting evidence for it is not provided.

The response should be JSON formatted as follows:
{{
    "points": [
        {{"description": "Description of point 1", "score": score_value}},
        {{"description": "Description of point 2", "score": score_value}}
    ]
}}
"""

PROMPTS[
    "global_reduce_rag_response"
] = """---Role---

You are a helpful assistant responding to questions about a dataset by synthesizing perspectives from multiple analysts.


---Goal---

Generate a response of the target length and format that responds to the user's question, summarize all the reports from multiple analysts who focused on different parts of the dataset.

Note that the analysts' reports provided below are ranked in the **descending order of importance**.

If you don't know the answer or if the provided reports do not contain sufficient information to provide an answer, just say so. Do not make anything up.

The final response should remove all irrelevant information from the analysts' reports and merge the cleaned information into a comprehensive answer that provides explanations of all the key points and implications appropriate for the response length and format.

Add sections and commentary to the response as appropriate for the length and format. Style the response in markdown.

The response shall preserve the original meaning and use of modal verbs such as "shall", "may" or "will".

Do not include information where the supporting evidence for it is not provided.


---Target response length and format---

{response_type}


---Analyst Reports---

{report_data}


---Goal---

Generate a response of the target length and format that responds to the user's question, summarize all the reports from multiple analysts who focused on different parts of the dataset.

Note that the analysts' reports provided below are ranked in the **descending order of importance**.

If you don't know the answer or if the provided reports do not contain sufficient information to provide an answer, just say so. Do not make anything up.

The final response should remove all irrelevant information from the analysts' reports and merge the cleaned information into a comprehensive answer that provides explanations of all the key points and implications appropriate for the response length and format.

The response shall preserve the original meaning and use of modal verbs such as "shall", "may" or "will".

Do not include information where the supporting evidence for it is not provided.


---Target response length and format---

{response_type}

Add sections and commentary to the response as appropriate for the length and format. Style the response in markdown.
"""

PROMPTS[
    "naive_rag_response"
] = """You're a helpful assistant
Below are the knowledge you know:
{content_data}
---
If you don't know the answer or if the provided knowledge do not contain sufficient information to provide an answer, just say so. Do not make anything up.
Generate a response of the target length and format that responds to the user's question, summarizing all information in the input data tables appropriate for the response length and format, and incorporating any relevant general knowledge.
If you don't know the answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.
---Target response length and format---
{response_type}
"""

PROMPTS["fail_response"] = "Sorry, I'm not able to provide an answer to that question."

PROMPTS["process_tickers"] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

PROMPTS["default_text_separator"] = [
    # Paragraph separators
    "\n\n",
    "\r\n\r\n",
    # Line breaks
    "\n",
    "\r\n",
    # Sentence ending punctuation
    "。",  # Chinese period
    "．",  # Full-width dot
    ".",  # English period
    "！",  # Chinese exclamation mark
    "!",  # English exclamation mark
    "？",  # Chinese question mark
    "?",  # English question mark
    # Whitespace characters
    " ",  # Space
    "\t",  # Tab
    "\u3000",  # Full-width space
    # Special characters
    "\u200b",  # Zero-width space (used in some Asian languages)
]
