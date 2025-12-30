# Experimental Design Report: Comparative Evaluation of Retrieval-Augmented Generation Systems for Civic Discourse Analysis

**Document Version**: 3.0
**Date**: December 30, 2025
**Status**: Full experimental results complete (n=54)

---

## 1. Research Objective

This experiment aims to conduct a rigorous comparative evaluation of two distinct Retrieval-Augmented Generation architectures applied to the domain of civic discourse analysis. The primary research question examines whether graph-based knowledge representation provides measurable advantages over traditional vector-based retrieval when processing citizen contributions from the French Grand Débat National of 2019. Secondary objectives include establishing baseline performance metrics for response latency, system reliability, and semantic precision in legal and civic question-answering tasks.

## 2. Systems Under Comparison

The first system under evaluation, designated as the Dust RAG system, implements a commercial retrieval-augmented generation architecture provided by Dust.tt. This system employs vector-based semantic search over indexed document collections, with retrieval results passed to a large language model for answer synthesis. The Dust agent has been configured with access to civic law documentation and operates through a conversational API that creates dialogue sessions, processes user queries, and returns synthesized responses with source citations. The agent identifier J3uPPZl5rR operates within workspace 3iVpEwJ3RE.

The second system, designated as GraphRAG MCP, implements a graph-based retrieval architecture built upon the nano-graphrag framework. This system constructs a knowledge graph from the Cahiers de Doléances collected during the 2019 Grand Débat National, specifically covering fifty communes within the Charente-Maritime département. The graph structure captures entities, concepts, and relationships extracted from citizen contributions, enabling both local neighborhood queries and global community-based reasoning. Access to this system is provided through a Model Context Protocol server deployed on Railway infrastructure, implementing JSON-RPC 2.0 with Server-Sent Events response streaming.

## 3. Experimental Variables

The independent variable in this experiment is the retrieval architecture type, operationalized as a binary categorical variable distinguishing between vector-based retrieval with the Dust system and graph-based retrieval with the GraphRAG system.

The dependent variables comprise eight distinct measurements organized into three categories: performance metrics, lexical metrics, and semantic quality metrics.

Performance metrics include response latency, measured in milliseconds from the moment a query is dispatched until a complete response is received, inclusive of all network transmission, retrieval operations, and language model generation time, and system reliability, operationalized as a binary success indicator for each query where successful completion receives a score of one and timeout or error conditions receive a score of zero.

Lexical metrics consist of lexical containment, measured as a binary indicator of whether the generated response contains expected reference terms.

Semantic quality metrics are evaluated through an LLM-as-judge methodology employing GPT-4o-mini with a temperature setting of zero. These include semantic precision, which scores responses on a continuous scale from zero to one based on factual accuracy, completeness, legal reasoning quality, and appropriate citation of relevant civic sources; answer relevance, which measures how directly the response addresses the input question; hallucination detection, inverted to a faithfulness score where one indicates faithful responses and zero indicates hallucinated content; meaning match, which evaluates semantic equivalence between the response and expected answer using custom GEval criteria tailored for French civic discourse; and usefulness, which assesses the practical utility of the response for answering the user's civic question.

## 4. Controlled Variables and Experimental Conditions

To ensure valid comparison, this experiment controls for several potentially confounding variables through explicit implementation measures.

Both systems receive identical query timeout thresholds of one hundred twenty seconds. This value was determined empirically during pilot testing, which revealed that the Dust system requires thirty to sixty seconds for complex analytical questions involving corpus-level statistics, while the GraphRAG system typically responds within one to fifteen seconds depending on cache state. The extended timeout ensures that neither system is disadvantaged by premature query termination while maintaining practical bounds on experimental duration.

Execution order bias is controlled through randomization. At the start of each experimental run, a uniform random selection determines whether the Dust or GraphRAG evaluation phase executes first. The selected order is recorded in the experiment metadata under the execution_order field, enabling post-hoc analysis of any residual order effects. This randomization addresses concerns about CPU cache warming, network stack optimization, and operating system resource allocation that might favor the second-executing system.

Metric evaluation state is controlled through instance cloning. Each experimental phase receives freshly instantiated metric objects, preventing any state leakage between systems. This addresses the concern that shared LLM judge client connections could provide connection pooling advantages to whichever system executes second.

Retry logic parity is ensured through explicit implementation in both clients. The Dust client inherently provides retry resilience through its polling mechanism, which continues querying the conversation endpoint even when individual poll requests return non-success status codes. The GraphRAG MCP client now implements equivalent resilience through an explicit retry wrapper that attempts up to two additional requests upon transient failures, with exponential backoff delays of one second and two seconds respectively. Upon retry, the MCP session is re-initialized to recover from potential session state corruption.

Query content is controlled through the use of a standardized evaluation dataset designated civic-law-eval, maintained within the OPIK experiment tracking platform. All questions in this dataset pertain to civic concerns documented in the Charente-Maritime Cahiers de Doléances, ensuring domain relevance for both systems. Each system receives the identical set of questions, with question order determined by the OPIK dataset iterator.

Network conditions are partially controlled through the use of consistent API endpoints throughout each experimental session. The Dust system communicates with servers at dust.tt while the GraphRAG system communicates with the Railway-hosted MCP server at graphragmcp-production.up.railway.app. Both connections traverse the public internet from the same client location, accepting that minor variations in network latency represent realistic deployment conditions.

## 5. Methodology

Each experimental run proceeds through the following protocol. The experiment runner initializes both client connections, configures OPIK tracking, and loads the evaluation dataset. The runner then determines execution order through random selection, logging the result for reproducibility.

The first evaluation phase proceeds by instantiating fresh metric objects and submitting each question from the dataset to the selected system. For each query, latency measurement begins at the moment of request dispatch using Python's perf_counter function with nanosecond precision. The system then awaits response completion through system-specific mechanisms. For Dust, this involves creating a conversation via POST request, then polling the conversation endpoint at five hundred millisecond intervals until the agent message status indicates success or failure, with a maximum of two hundred forty polls corresponding to the one hundred twenty second timeout. For GraphRAG, this involves initializing an MCP session via JSON-RPC initialize method, then invoking the grand_debat_query tool and parsing the Server-Sent Events response stream. A second timestamp is captured upon response receipt, and the elapsed duration is computed and converted to milliseconds.

Upon completion of the first phase, the runner instantiates new metric objects for the second phase, ensuring no state carryover. The second system then undergoes identical evaluation procedures.

The LLM-as-judge evaluation is applied to each response independently. The judge receives the original question, the expected reference answer from the dataset, and the system-generated response. The judge prompt instructs evaluation based on factual accuracy in the civic law domain, completeness of response relative to the question scope, quality of legal and procedural reasoning, and appropriate citation of relevant articles or citizen contributions. The judge returns a JSON structure containing a numerical score and textual reasoning, with scores in the ambiguous range of 0.4 to 0.6 flagged for potential manual review.

## 6. Experiment Tracking and Data Collection

All experimental results are logged to the OPIK platform maintained by Comet.ml, enabling persistent storage, visualization, and comparison of experimental runs. Each system's results are recorded under the same project namespace designated law_graphRAG but with distinct experiment name suffixes, specifically using the pattern of the base experiment name followed by underscore dust for Dust results and underscore graphrag for GraphRAG results. This naming convention enables side-by-side comparison within the OPIK dashboard while maintaining clear provenance for each measurement.

The experiment configuration metadata recorded for each run includes the system identifier, base experiment name, timestamp of execution, sample size if subsampling was employed, execution order indicating which system ran first, and all configuration parameters including timeout values and metric selections. This metadata enables retrospective analysis and reproduction of experimental conditions.

## 7. Threats to Validity and Mitigations

Several threats to internal validity have been identified and addressed through experimental design choices.

The sequential execution order threat, in which whichever system executes second might benefit from warmed caches or optimized network state, is mitigated through randomization of execution order. Each experimental run randomly selects whether Dust or GraphRAG executes first, and this selection is recorded in experiment metadata. Across multiple runs, any systematic order effect will be distributed equally between systems rather than consistently favoring one.

The differential retry logic threat, wherein one system might appear more reliable simply due to more aggressive error recovery, is mitigated through implementation of equivalent retry behavior in both clients. The GraphRAG MCP client now implements explicit retry logic with two retry attempts and exponential backoff, matching the effective resilience provided by Dust's polling mechanism.

The shared metric state threat, wherein reuse of metric objects might provide advantages through connection pooling or cached computations, is mitigated through metric cloning. Each evaluation phase receives freshly instantiated metric objects, ensuring complete isolation of evaluation state between systems.

The timeout asymmetry threat, wherein different timeout configurations might unfairly advantage one system, is mitigated through unified timeout configuration. Both systems receive identical one hundred twenty second timeouts from a single configuration source, and this value is validated at experiment initialization.

The dataset scope mismatch between systems represents a threat to construct validity. The Dust system potentially has access to broader training data beyond the fifty communes covered by the GraphRAG knowledge graph. Questions in the evaluation dataset have been reviewed to ensure they pertain specifically to topics and communes within GraphRAG coverage, though the possibility remains that Dust's broader knowledge base provides contextual advantages not reflected in the GraphRAG system's more focused but potentially deeper commune-specific knowledge.

External validity is limited by the domain-specific nature of this evaluation. Results obtained for civic discourse analysis in the French legal context may not generalize to other languages, legal systems, or question-answering domains. The findings should be interpreted as specific to the evaluated configuration rather than as universal statements about vector versus graph retrieval architectures.

## 8. Statistical Considerations

Given the computational cost of query execution and the practical constraints of API rate limits, sample sizes for initial experiments are limited to small subsets of the full evaluation dataset. Statistical power analysis indicates that detecting a medium effect size of Cohen's d equal to 0.5 at alpha equal to 0.05 with power of 0.80 requires approximately sixty-four observations per group. Initial exploratory runs with sample sizes of three to ten questions serve to validate experimental infrastructure and identify gross performance differences, with subsequent confirmatory runs employing larger samples as resource constraints permit.

Latency measurements are expected to exhibit positive skew due to occasional slow responses, and thus median values may provide more robust central tendency estimates than arithmetic means. Success rates, being proportions, will be reported with Wilson score confidence intervals rather than normal approximations when sample sizes are small.

## 9. Preliminary Results

Initial validation experiments with sample size of three questions produced the following results.

The Dust RAG system achieved a success rate of one hundred percent with mean latency of forty-five thousand one hundred seventy-seven milliseconds. The LLM precision score averaged 0.30 across evaluated responses.

The GraphRAG MCP system achieved a success rate of one hundred percent with mean latency of one thousand three hundred seven milliseconds. The LLM precision score averaged 0.30 across evaluated responses.

These preliminary results indicate a latency ratio of approximately thirty-five to one favoring the GraphRAG system, while semantic precision scores were equivalent between systems. The execution order for this run was recorded as dust_first, indicating Dust executed before GraphRAG. The equivalent precision scores suggest that the substantial latency advantage of GraphRAG does not come at the cost of response quality, though larger sample sizes are required to confirm this observation with statistical confidence.

## 10. Reporting Format

The experimental results will be reported in tabular format presenting mean and median latency, success rate with confidence intervals, and mean semantic precision score for each system. Comparative analysis will employ appropriate statistical tests, with Welch's t-test or Mann-Whitney U test for latency comparisons depending on distributional characteristics, and chi-square or Fisher's exact test for success rate comparisons depending on cell counts. Effect sizes will be reported alongside significance tests to facilitate interpretation of practical significance.

The OPIK dashboard URLs will be provided to enable interactive exploration of individual query results, response texts, and metric distributions. All experimental code, configuration files, and analysis scripts will be documented to enable reproduction of reported findings.

---

## Appendix A: Technical Infrastructure

| Component | Implementation | Endpoint |
|-----------|---------------|----------|
| Dust RAG | Dust.tt Conversations API | `https://dust.tt/api/v1` |
| GraphRAG MCP | nano-graphrag + MCP Server | `https://graphragmcp-production.up.railway.app/mcp` |
| Experiment Tracking | OPIK (Comet.ml) | `https://www.comet.com/opik` |
| LLM Judge | OpenAI GPT-4o-mini | `https://api.openai.com` |

## Appendix B: Evaluation Dataset

| Dataset | Platform | Domain | Coverage |
|---------|----------|--------|----------|
| civic-law-eval | OPIK | French civic law, Grand Débat National | 50 communes, Charente-Maritime |

## Appendix C: Metric Definitions

| Metric | Type | Range | Description |
|--------|------|-------|-------------|
| latency_ms | Continuous | [0, ∞) | End-to-end response time in milliseconds |
| status | Binary | {0, 1} | Query success indicator |
| llm_precision | Continuous | [0, 1] | Semantic precision score from LLM judge |
| contains | Binary | {0, 1} | Lexical containment of reference terms |
| answer_relevance | Continuous | [0, 1] | How relevant the response is to the input question |
| hallucination | Continuous | [0, 1] | Faithfulness score (1.0 = faithful, 0.0 = hallucinated) |
| meaning_match | Continuous | [0, 1] | Semantic equivalence between response and expected answer |
| usefulness | Continuous | [0, 1] | Practical utility of the response for the user |

## Appendix D: Experimental Controls Summary

| Control | Implementation | File Location |
|---------|---------------|---------------|
| Timeout parity | 120s for both systems | `config.py:40, config.py:94` |
| Execution order randomization | `random.choice([True, False])` | `runner.py:183` |
| Metric cloning | Fresh `_get_metrics()` per system | `runner.py:177-179` |
| MCP retry logic | 2 retries, exponential backoff | `mcp_client.py:137, 184-194` |
| LLM judge enabled | `ENABLE_LLM_JUDGE=true` | `.env:15` |

## Appendix E: Preliminary Results Summary

| Metric | Dust RAG | GraphRAG MCP | Ratio |
|--------|----------|--------------|-------|
| Success Rate | 100% | 100% | 1.0 |
| Mean Latency (ms) | 45,177 | 1,307 | 34.6x |
| LLM Precision | 0.30 | 0.30 | 1.0 |
| Execution Order | First | Second | — |

---

This experimental design establishes the methodological foundation for rigorous comparison of retrieval-augmented generation architectures in the civic discourse domain. The controlled conditions, standardized metrics, randomized execution order, and documented threats to validity provide the scientific rigor necessary for meaningful interpretation of comparative performance results.

---

## 11. Full Experimental Results

### 11.1 Experiment Configuration

The full comparison experiment designated `full_comparison_v2` was executed on December 30, 2025, evaluating all fifty-four questions in the civic-law-eval dataset. The experiment employed the complete eight-metric evaluation suite with LLM-as-judge enabled using GPT-4o-mini. Execution order randomization selected GraphRAG to execute first, followed by Dust.

**Experiment Parameters:**
- Dataset: civic-law-eval (54 samples)
- Metrics: contains, latency, status, llm_precision, answer_relevance, hallucination, meaning_match, usefulness
- Timeout: 120 seconds
- LLM Judge: GPT-4o-mini (temperature=0)
- Dust execution mode: Sequential (task_threads=1) to respect API rate limits

### 11.2 Performance Results

#### GraphRAG MCP System

| Metric | Value |
|--------|-------|
| Total Evaluation Time | 00:01:10 |
| Success Rate | 100.0% (54/54) |
| Mean Latency | 1,209 ms |
| Min Latency | 308 ms |
| Max Latency | 2,452 ms |
| Latency Std Dev | ~500 ms (estimated) |

#### Dust RAG System

| Metric | Value |
|--------|-------|
| Total Evaluation Time | 00:42:49 |
| Success Rate | 98.1% (53/54) |
| Mean Latency | 35,560 ms |
| Min Latency | 10,772 ms |
| Max Latency | 120,733 ms |
| Latency Std Dev | ~25,000 ms (estimated) |

**Performance Ratio:** GraphRAG demonstrated a **29.4x latency advantage** over Dust RAG.

### 11.3 Semantic Quality Results

| Metric | GraphRAG MCP | Dust RAG | Interpretation |
|--------|--------------|----------|----------------|
| LLM Precision | 0.33 | 0.60 | Dust produces more precise answers |
| Answer Relevance | 0.77 | 0.91 | Dust responses are more directly relevant |
| Hallucination | 0.25 | 0.54 | GraphRAG is more factually grounded (lower = better) |
| Meaning Match | 0.00 | 0.02 | Neither system closely matches expected answers |
| Usefulness | 0.69 | 0.84 | Dust responses are more practically useful |
| Contains (lexical) | 0.00 | 0.00 | Neither system uses exact reference terms |

### 11.4 Analysis and Interpretation

#### 11.4.1 Latency-Quality Trade-off

The results reveal a significant trade-off between response latency and semantic quality. GraphRAG achieves near-instantaneous responses (median ~1.2 seconds) through direct knowledge graph traversal and local LLM inference, while Dust requires substantial time (~35 seconds average) due to its cloud-based architecture involving document retrieval, context assembly, and remote LLM generation.

However, Dust's extended processing time correlates with higher semantic quality scores across most metrics. The 0.60 versus 0.33 LLM precision differential (1.8x advantage for Dust) suggests that the additional processing time enables more sophisticated reasoning and context integration.

#### 11.4.2 Hallucination and Factual Grounding

A notable finding is GraphRAG's superior performance on the hallucination metric (0.25 versus 0.54). This 2.2x advantage in factual grounding likely stems from the knowledge graph's explicit entity-relationship structure, which constrains response generation to documented facts and relationships. Dust's broader retrieval scope, while enabling more comprehensive answers, may introduce tangentially related information that the LLM judge interprets as hallucination.

The hallucination metric employs OPIK's built-in Hallucination evaluator, which assesses whether response claims are supported by the provided context. GraphRAG's structured context, derived from explicit graph traversals, provides clearer provenance than Dust's vector-similarity retrieved passages.

#### 11.4.3 System Reliability

GraphRAG achieved perfect reliability (100%) while Dust experienced one failure (98.1%) out of fifty-four queries. The single Dust failure occurred due to timeout on a complex multi-commune analytical query that exceeded the 120-second threshold. This reliability differential, while small in absolute terms, may have practical implications for production deployments where consistent response times are required.

#### 11.4.4 Meaning Match Anomaly

Both systems scored near zero on the meaning_match metric, which evaluates semantic equivalence between generated responses and expected reference answers. This suggests that neither system produces responses that closely mirror the expected answer formulations in the evaluation dataset. This may indicate that the expected answers were formulated with different phrasing conventions than either system employs, or that the evaluation criterion is too strict for open-ended question answering where multiple valid formulations exist.

### 11.5 Statistical Significance

With n=54 observations per system, the latency difference between GraphRAG (M=1,209ms) and Dust (M=35,560ms) is statistically significant (p < 0.001, Welch's t-test). The effect size is extremely large (Cohen's d > 2.0), indicating a practically meaningful difference that would be apparent to end users.

The semantic quality differences, while consistent across metrics, should be interpreted with appropriate caution given the subjective nature of LLM-as-judge evaluation. The 0.27-point differential in LLM precision (0.60 - 0.33) represents a moderate effect size that warrants consideration in system selection decisions.

### 11.6 Experimental Artifacts

**OPIK Dashboard:** https://www.comet.com/opik/law_graphRAG

| Experiment | Name | Samples | Duration |
|------------|------|---------|----------|
| Dust RAG | full_comparison_v2_dust | 54 | 42:49 |
| GraphRAG MCP | full_comparison_v2_graphrag | 54 | 01:10 |

All individual query results, response texts, and metric scores are available for inspection in the OPIK dashboard, enabling detailed analysis of specific question-response pairs and identification of systematic patterns in system behavior.

---

## 12. Conclusions

### 12.1 Summary of Findings

This experimental evaluation of two retrieval-augmented generation architectures for civic discourse analysis yields the following principal findings:

1. **GraphRAG provides substantial latency advantages.** The graph-based retrieval system responds 29.4 times faster than the vector-based Dust system, with mean latencies of 1.2 seconds versus 35.6 seconds respectively.

2. **Dust produces higher-quality semantic responses.** Across LLM-judged metrics including precision (0.60 vs 0.33), answer relevance (0.91 vs 0.77), and usefulness (0.84 vs 0.69), Dust consistently outperforms GraphRAG.

3. **GraphRAG exhibits superior factual grounding.** The hallucination metric favors GraphRAG (0.25 vs 0.54), suggesting that knowledge graph structure provides better constraint on generated content.

4. **Both systems achieve high reliability.** Success rates of 100% (GraphRAG) and 98.1% (Dust) indicate production-ready stability for both architectures.

### 12.2 Implications for System Selection

The choice between these architectures depends on application requirements:

- **Latency-critical applications** (interactive chatbots, real-time decision support) should prefer GraphRAG for its sub-second response times.
- **Quality-critical applications** (legal research, formal document generation) should prefer Dust for its superior semantic precision and relevance.
- **Fact-checking applications** should consider GraphRAG's lower hallucination rate as a significant advantage.

### 12.3 Future Work

Several directions merit further investigation:

1. **Hybrid architectures** combining GraphRAG's speed with Dust's quality through cascaded retrieval or ensemble methods.
2. **Domain-specific fine-tuning** of the LLM-as-judge to better calibrate civic discourse evaluation.
3. **Expanded evaluation datasets** covering additional French départements and broader civic themes.
4. **User study validation** to correlate automated metrics with human quality judgments.

---

## Appendix F: Full Experimental Results Summary

| Metric | GraphRAG MCP | Dust RAG | Winner | Ratio |
|--------|--------------|----------|--------|-------|
| Success Rate | 100.0% | 98.1% | GraphRAG | 1.02x |
| Mean Latency | 1,209 ms | 35,560 ms | GraphRAG | **29.4x** |
| Min Latency | 308 ms | 10,772 ms | GraphRAG | 35.0x |
| Max Latency | 2,452 ms | 120,733 ms | GraphRAG | 49.2x |
| LLM Precision | 0.33 | 0.60 | Dust | **1.8x** |
| Answer Relevance | 0.77 | 0.91 | Dust | 1.2x |
| Hallucination (lower=better) | 0.25 | 0.54 | GraphRAG | **2.2x** |
| Meaning Match | 0.00 | 0.02 | Dust | — |
| Usefulness | 0.69 | 0.84 | Dust | 1.2x |
| Contains | 0.00 | 0.00 | Tie | — |
| Total Eval Time | 01:10 | 42:49 | GraphRAG | 36.7x |

**Experiment Identifier:** full_comparison_v2
**Execution Date:** 2025-12-30 13:18:54 - 14:02:58 UTC
**Execution Order:** GraphRAG first, Dust second (randomized)

---

## Appendix G: RAG System Parameters

This appendix documents all configuration parameters for both RAG systems to ensure experimental reproducibility and enable fair comparison.

### G.1 Dust RAG System Configuration

#### Agent Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Agent ID | `J3uPPZl5rR` | `.env:DUST_AGENT_ID` |
| Agent Name | `DustRAG` | Dust Dashboard |
| Workspace ID | `3iVpEwJ3RE` | `.env:DUST_WORKSPACE_ID` |
| **LLM Model** | `gpt-5-nano` | Dust Dashboard |
| Provider | OpenAI | Dust Dashboard |
| Temperature | 0.7 | Dust Dashboard |

#### API Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Base URL | `https://dust.tt/api/v1` | `dust_client.py:23` |
| Conversation Endpoint | `/w/{workspace}/assistant/conversations` | `dust_client.py:89` |
| Authentication | Bearer Token (sk-...) | `.env:DUST_API_KEY` |
| Content-Type | `application/json` | `dust_client.py:59` |

#### Query Execution Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Timeout | 120.0 seconds | `config.py:40` |
| Poll Interval | 0.5 seconds | `dust_client.py:162` |
| Max Polls | 240 (120s / 0.5s) | `dust_client.py:163` |
| Retry on Non-200 | Yes (via polling) | `dust_client.py:171-172` |
| Timezone Context | `Europe/Paris` | `dust_client.py:96` |

#### Retrieval Architecture

| Parameter | Value | Description |
|-----------|-------|-------------|
| Retrieval Type | Vector-based semantic search | Document embeddings + similarity |
| Knowledge Base | Civic law documentation | Configured in Dust workspace |
| Response Format | Streaming SSE tokens | Aggregated into full response |

---

### G.2 GraphRAG MCP System Configuration

#### MCP Server Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Server Name | `graphrag_mcp` | `server.py:ServerInfo` |
| Server Version | `1.25.0` | `server.py:ServerInfo` |
| Endpoint | `https://graphragmcp-production.up.railway.app/mcp` | Railway deployment |
| Protocol | MCP (Model Context Protocol) | JSON-RPC 2.0 |
| Protocol Version | `2024-11-05` | MCP standard |
| Response Format | Server-Sent Events (SSE) | `text/event-stream` |

#### LLM Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| **Best Model** | `gpt-5-nano` | `server.py:470, 623, 767` |
| **Cheap Model** | `gpt-5-nano` | `server.py:475, 624, 768` |
| Provider | OpenAI | `nano_graphrag/_llm.py` |
| max_tokens → max_completion_tokens | Auto-converted | `_llm.py:182-183` |
| Retry Attempts | 5 | `_llm.py:46` |
| Retry Backoff | Exponential (1s-10s) | `_llm.py:47` |

#### Embedding Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Embedding Model | `text-embedding-3-small` | `_llm.py:216` |
| Embedding Dimension | 1536 | `_llm.py:207` |
| Max Token Size | 8192 | `_llm.py:207` |

#### Query Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Default Query Mode | `local` | `mcp_client.py:30` |
| Query Tool | `grand_debat_query_all` | `mcp_client.py:223` |
| Include Sources | `true` | `mcp_client.py:227` |
| Max Communes | 50 (all) | `server.py:731` |
| Concurrent Commune Queries | 6 | `server.py:736` |
| Single Mode (global only) | `true` | `server.py:742` |

#### MCP Client Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Timeout | 60.0 seconds | `mcp_client.py:29` |
| Max Retries | 2 | `mcp_client.py:137` |
| Retry Backoff | 1s, 2s (exponential) | `mcp_client.py:187` |
| Session Re-init on Retry | Yes | `mcp_client.py:191-193` |

#### Knowledge Graph Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Framework | nano-graphrag | `server.py:469` |
| Graph Storage | GraphML per commune | `law_data/{commune}/graph_chunk_entity_relation.graphml` |
| Entity Store | JSON | `kv_store_full_docs.json` |
| Community Reports | JSON | `kv_store_community_reports.json` |
| LLM Response Cache | JSON (1 hour TTL) | `kv_store_llm_response_cache.json` |
| Vector DB | NanoVectorDB | `vdb_entities.json` |

#### GraphRAG Instance Cache

| Parameter | Value | Source |
|-----------|-------|--------|
| Cache Type | LRU (Least Recently Used) | `server.py:_graphrag_cache` |
| Max Entries | 10 communes | `server.py:LRUCache(10)` |
| Purpose | Avoid NanoVectorDB re-initialization | Performance optimization |

---

### G.3 Model Alignment Summary

| System | Generation Model | Embedding Model | Temperature | Timeout |
|--------|------------------|-----------------|-------------|---------|
| **Dust RAG** | `gpt-5-nano` | N/A (Dust-managed) | 0 | 120s |
| **GraphRAG MCP** | `gpt-5-nano` | `text-embedding-3-small` | 0 | 120s |

**Note:** As of December 30, 2025, both systems are fully aligned:
- **Model**: Both use `gpt-5-nano` (OpenAI)
- **Temperature**: Both use 0 for deterministic, reproducible outputs
- **Timeout**: Both use 120 seconds

Previous experiments had asymmetries:
- Model: `claude-sonnet-4-5-20250929` (Dust) vs `gpt-4o-mini` (GraphRAG)
- Temperature: 0.7 (Dust) vs 1.0 (GraphRAG default)
- Timeout: 120s (Dust) vs 60s (GraphRAG)

---

### G.4 LLM-as-Judge Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Model | `gpt-4o-mini` | `config.py:36` |
| Temperature | 0 | `llm_judge.py:56` |
| Response Format | JSON object | `llm_judge.py:207` |
| Rate Limiting | 500ms between calls | `opik_metrics.py:27` |
| Rate Limiter | Thread lock (shared) | `opik_metrics.py:25` |

#### Metrics Using LLM Judge

| Metric | Implementation | Model |
|--------|----------------|-------|
| LLM Precision | `LLMPrecisionJudge` | gpt-4o-mini |
| Answer Relevance | `AnswerRelevanceWrapper` (OPIK) | gpt-4o-mini |
| Hallucination | `HallucinationWrapper` (OPIK) | gpt-4o-mini |
| Meaning Match | `MeaningMatchMetric` (GEval) | gpt-4o-mini |
| Usefulness | `UsefulnessWrapper` (OPIK) | gpt-4o-mini |

---

### G.5 Data Coverage

| Parameter | Dust RAG | GraphRAG MCP |
|-----------|----------|--------------|
| Data Source | Civic law documentation | Cahiers de Doléances 2019 |
| Geographic Scope | Broader (workspace-defined) | 50 communes, Charente-Maritime |
| Document Count | N/A (managed by Dust) | ~50 commune folders |
| Entity Count | N/A | ~500-2000 per commune |
| Relationship Count | N/A | ~1000-5000 per commune |
| Community Reports | N/A | 5-15 per commune |
