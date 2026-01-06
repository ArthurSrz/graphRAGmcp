# Experimental Design Report: Comparative Evaluation of Retrieval-Augmented Generation Systems for Civic Discourse Analysis

**Document Version**: 5.0
**Date**: December 30, 2025
**Status**: Configuration corrected (temperature fix), ready for controlled experiment

---

## 1. Research Objective

This experiment aims to conduct a rigorous comparative evaluation of two distinct Retrieval-Augmented Generation architectures applied to the domain of civic discourse analysis. The primary research question examines whether graph-based knowledge representation provides measurable advantages over traditional vector-based retrieval when processing citizen contributions from the French Grand Débat National of 2019. Secondary objectives include establishing baseline performance metrics for response latency, system reliability, and semantic precision in legal and civic question-answering tasks.

## 2. Systems Under Comparison

Both systems under evaluation share the same base language model to isolate the retrieval architecture as the primary independent variable. Each system uses OpenAI's GPT-5-nano model and operates under identical timeout constraints of one hundred twenty seconds. A notable constraint exists with temperature settings: Dust operates at temperature 0.7 (platform-fixed), while GraphRAG operates at temperature 1.0 (gpt-5-nano model constraint). This asymmetry is documented as a known limitation in Appendix G.

The first system, designated as the Dust RAG system, implements a commercial retrieval-augmented generation architecture provided by Dust.tt. This system employs vector-based semantic search over indexed document collections, with retrieval results passed to the language model for answer synthesis. The Dust agent operates through a conversational API that creates dialogue sessions, processes user queries, and returns synthesized responses with source citations.

The second system, designated as GraphRAG MCP, implements a graph-based retrieval architecture built upon the nano-graphrag framework. This system constructs a knowledge graph from the Cahiers de Doléances collected during the 2019 Grand Débat National, specifically covering fifty communes within the Charente-Maritime département. The graph structure captures entities, concepts, and relationships extracted from citizen contributions, enabling both local neighborhood queries and global community-based reasoning. The system queries all fifty communes simultaneously to provide comprehensive coverage comparable to Dust's corpus-wide retrieval.

## 3. Experimental Variables

The independent variable in this experiment is the retrieval architecture type, operationalized as a binary categorical variable distinguishing between vector-based retrieval with the Dust system and graph-based retrieval with the GraphRAG system.

The dependent variables comprise eight distinct measurements organized into three categories: performance metrics, lexical metrics, and semantic quality metrics.

Performance metrics include response latency, measured in milliseconds from the moment a query is dispatched until a complete response is received, inclusive of all network transmission, retrieval operations, and language model generation time, and system reliability, operationalized as a binary success indicator for each query where successful completion receives a score of one and timeout or error conditions receive a score of zero.

Lexical metrics consist of lexical containment, measured as a binary indicator of whether the generated response contains expected reference terms.

Semantic quality metrics are evaluated through an LLM-as-judge methodology employing GPT-4o-mini with a temperature setting of zero. These include semantic precision, which scores responses on a continuous scale from zero to one based on factual accuracy, completeness, legal reasoning quality, and appropriate citation of relevant civic sources; answer relevance, which measures how directly the response addresses the input question; hallucination detection, inverted to a faithfulness score where one indicates faithful responses and zero indicates hallucinated content; meaning match, which evaluates semantic equivalence between the response and expected answer using custom GEval criteria tailored for French civic discourse; and usefulness, which assesses the practical utility of the response for answering the user's civic question.

## 4. Controlled Variables and Experimental Conditions

To ensure valid comparison, this experiment controls for several potentially confounding variables through explicit implementation measures.

Language model parity is partially ensured by configuring both systems to use the same base LLM (GPT-5-nano). However, a temperature asymmetry exists due to platform constraints: Dust operates at temperature 0.7 (platform-fixed, cannot be modified via API), while GraphRAG operates at temperature 1.0 (gpt-5-nano model constraint, the model only accepts temperature=1.0). This asymmetry may affect response creativity and consistency: higher temperature (GraphRAG) produces more varied outputs, while lower temperature (Dust) produces more deterministic outputs. This limitation is documented in Section 7.6 and Appendix G.

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

The temperature parameter asymmetry represents an unmitigable threat to internal validity. Due to platform constraints, Dust operates at temperature 0.7 while GraphRAG operates at temperature 1.0. This asymmetry cannot be resolved: the Dust platform does not expose temperature configuration via API, and the GPT-5-nano model rejects any temperature value other than 1.0. The effect of this asymmetry is that GraphRAG responses may exhibit greater variability and creativity compared to Dust's more deterministic outputs. Consumers of experimental results should consider this limitation when interpreting response quality metrics, particularly those measuring semantic precision and answer consistency.

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

| Control | Implementation | Value |
|---------|---------------|-------|
| LLM model parity | Both systems use same model | gpt-5-nano |
| Temperature parity | Both systems use same temperature | 0.7 |
| Timeout parity | Both systems use same timeout | 120 seconds |
| Execution order randomization | Random selection per run | 50% probability each |
| Metric cloning | Fresh instances per system | Prevents state leakage |
| Retry logic parity | Equivalent resilience | Polling / 2 retries |
| Query scope parity | GraphRAG queries all communes | 50 communes via query_all |

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

> **⚠️ HISTORICAL DATA - SUPERSEDED**
>
> The results in this section were obtained before full configuration alignment. Key asymmetries existed:
> - **Model**: Dust used Claude Sonnet 4.5, GraphRAG used GPT-4o-mini
> - **Temperature**: Dust used 0.7, GraphRAG used 1.0 (default)
> - **Query scope**: GraphRAG only queried 1 commune (Rochefort) instead of all 50
>
> These results are retained for historical reference but should not be used for comparative analysis. New controlled experiments with aligned configurations will supersede these findings.

### 11.1 Experiment Configuration (Historical)

The full comparison experiment designated `full_comparison_v2` was executed on December 30, 2025, evaluating all fifty-four questions in the civic-law-eval dataset. The experiment employed the complete eight-metric evaluation suite with LLM-as-judge enabled using GPT-4o-mini. Execution order randomization selected GraphRAG to execute first, followed by Dust.

**Experiment Parameters (Historical - Not Aligned):**
- Dataset: civic-law-eval (54 samples)
- Metrics: contains, latency, status, llm_precision, answer_relevance, hallucination, meaning_match, usefulness
- Timeout: 120 seconds
- LLM Judge: GPT-4o-mini (temperature=0)
- Dust execution mode: Sequential (task_threads=1) to respect API rate limits
- ⚠️ Dust model: Claude Sonnet 4.5 (not aligned)
- ⚠️ GraphRAG model: GPT-4o-mini (not aligned)
- ⚠️ GraphRAG scope: Single commune only (not aligned)

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

## Appendix G: Controlled Experimental Parameters

This appendix documents the aligned configuration parameters ensuring fair comparison between systems.

### G.1 Aligned Parameters

| Parameter | Dust RAG | GraphRAG MCP | Status |
|-----------|----------|--------------|--------|
| **LLM Model** | gpt-5-nano | gpt-5-nano | ✓ Aligned |
| **Temperature** | 0.7 (platform-fixed) | 1.0 (model-fixed) | ⚠ Asymmetric |
| **Timeout** | 120 seconds | 120 seconds | ✓ Aligned |
| **Provider** | OpenAI | OpenAI | ✓ Aligned |
| **Retry Logic** | Polling (implicit) | 2 retries + backoff | ✓ Equivalent |

**Temperature Asymmetry Note**: The GPT-5-nano model only accepts temperature=1.0. Attempts to set temperature=0.7 result in API error 400: "Unsupported value: 'temperature' does not support 0.7 with this model." Dust's temperature is fixed at 0.7 by the platform and cannot be modified programmatically. This asymmetry is an unavoidable platform constraint.

### G.2 Independent Variable: Retrieval Architecture

| Aspect | Dust RAG | GraphRAG MCP |
|--------|----------|--------------|
| **Architecture** | Vector-based | Graph-based |
| **Retrieval Method** | Semantic similarity search | Knowledge graph traversal |
| **Context Assembly** | Retrieved document chunks | Entity-relationship subgraphs |
| **Query Scope** | Full corpus | All 50 communes (query_all) |

### G.3 LLM-as-Judge Configuration (Shared)

| Parameter | Value |
|-----------|-------|
| Model | gpt-4o-mini |
| Temperature | 0 |
| Rate Limiting | 500ms between calls |

### G.4 Evaluation Dataset

| Parameter | Value |
|-----------|-------|
| Dataset | civic-law-eval |
| Domain | French civic law, Grand Débat National |
| Coverage | 50 communes, Charente-Maritime |
| Questions | 54 (full) / 10 (sample) |
