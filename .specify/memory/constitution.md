<!--
SYNC IMPACT REPORT
==================
Version Change: 0.0.0 → 1.0.0 (Initial ratification)
Ratification Date: 2026-01-06
Last Amended: 2026-01-06

Modified Principles: N/A (initial version)
Added Sections: All (initial constitution)
Removed Sections: None

Templates Requiring Updates:
✅ spec-template.md - Reviewed, principles align with user story prioritization
✅ plan-template.md - Reviewed, constitutional check gate present
✅ tasks-template.md - Reviewed, user story organization aligns with incremental delivery
✅ commands/*.md - Reviewed, constitution command workflow correct

Follow-up TODOs: None
-->

# GraphRAG MCP Server Constitution

## Core Principles

### I. Graph-First Architecture

Every feature treats knowledge graphs as first-class data structures with pre-computed adjacency indices. Graph traversal MUST achieve O(1) neighbor lookups through in-memory adjacency lists. Per-query GraphML parsing is prohibited—all graph data MUST be loaded at server initialization.

**Rationale**: The 50x performance improvement documented in troubleshooting.md (25-30s → 0.5s per query) demonstrates that graph-first design with pre-computation is non-negotiable for production deployment. The GraphIndex class (graph_index.py) embodies this principle by loading all commune graphs at startup and maintaining in-memory indices.

### II. No Orphan Nodes (Commune-Centric Design)

Entities without relationships MUST be filtered from all graph operations. Every node in the graph MUST have at least one edge. All entities MUST track their source commune via metadata. Graph queries and visualizations MUST center around core entities (communes, themes, concepts) rather than peripheral nodes.

**Rationale**: Design constraint 1 from CLAUDE.md explicitly requires that orphan nodes are not allowed in the interface. This ensures that the knowledge graph represents meaningful semantic relationships rather than isolated facts. The GraphIndex explicitly stores source_commune per entity (line 209-215 in graph_index.py) to maintain provenance.

### III. Provenance & End-to-End Interpretability

Every GraphRAG response MUST be traceable from text chunks through entities to the final answer. Chunks are first-class graph citizens connected via HAS_SOURCE edges. Source quotes MUST be retrievable through graph traversal without file I/O during query execution. The system MUST maintain complete audit trails from citizen contributions to LLM responses.

**Rationale**: Design constraint 5 from CLAUDE.md mandates end-to-end interpretability, allowing navigation from text chunks to RAG responses through nodes and relationships. The chunk optimization (troubleshooting.md "Fast Graph Traversal to Chunks") demonstrates that chunks are treated as entities with bidirectional edges, enabling O(1) provenance lookup. This architectural decision reduced chunk retrieval from 500ms+ file I/O to <1ms in-memory traversal.

### IV. MCP Protocol Compliance

All GraphRAG capabilities MUST be exposed as MCP tools following the Model Context Protocol specification. Tools MUST use flat parameter signatures with `Annotated` types (NOT nested Pydantic models) for client compatibility. Session management MUST follow JSON-RPC 2.0 with Server-Sent Events for streaming responses.

**Rationale**: The "Pydantic Validation Error" troubleshooting entry documents that nested params break Dust.tt and other MCP clients. Flat parameters ensure universal client compatibility. The server implements TransportSecuritySettings with dns_rebinding_protection=False for reverse proxy compatibility (Railway/Cloud Run deployment pattern).

### V. Performance by Design (Documented Optimization)

Performance improvements MUST be documented in troubleshooting.md with problem description, root cause analysis, solution implementation, and measured impact. New features MUST include baseline performance metrics. Regressions caught in testing MUST be investigated and resolved before merge.

**Rationale**: The troubleshooting.md file serves as a living architectural history, documenting 7 major optimization efforts with quantified improvements. This practice ensures that performance decisions are not lost and regressions can be detected. Examples include LLM cache singleton (-5-20s for overlapping queries) and dual-strategy retrieval (16% → 92.7% corpus coverage).

### VI. Empirical Validation with LLM-as-Judge

Changes to retrieval strategies MUST be validated using the OPIK evaluation framework with GPT-4o-mini as judge. Evaluation MUST include quantitative metrics: meaning_match, hallucination, answer_relevance, and latency. A/B comparisons MUST control for model, temperature, timeout, and execution order. Results MUST be logged to OPIK with experiment tags for reproducibility.

**Rationale**: The experimental-design-rag-comparison.md document demonstrates systematic A/B testing that revealed the 9-commune limitation bug (meaning_match: 0.037 → 0.60+ after fix). This empirical approach prevents performance regressions and validates architectural changes. The server includes OPIK integration (lines 48-156 in server.py) with async judge evaluation to measure semantic quality without blocking query responses.

### VII. Iterative Problem-Solving (Architecture Through Debugging)

Major architectural decisions MUST be captured in troubleshooting.md when they emerge through bug resolution. Each entry MUST include: Problem description with symptoms, Root cause analysis with code references, Solution implementation with snippets, Performance impact with before/after metrics, Date fixed for historical tracking.

**Rationale**: Reviewing troubleshooting.md reveals that key architectural insights emerged through debugging rather than upfront design. The GraphML source_id attribute discovery (99.85% failure → 93.7% coverage) fundamentally changed how chunks are accessed. This principle acknowledges that complex systems reveal their optimal architecture through iterative refinement, and that architectural knowledge must be captured when bugs expose design flaws.

## Technical Standards

### Deployment & Infrastructure

- **Cloud-Native Deployment**: Server MUST support Railway and Cloud Run deployment with environment-based configuration (OPENAI_API_KEY, GRAND_DEBAT_DATA_PATH, OPIK_API_KEY). Reverse proxy compatibility MUST be maintained through proxy_headers=True and forwarded_allow_ips="*" in uvicorn configuration.

- **Observability**: All query executions MUST log to OPIK with metadata including latency_ms, mode, commune_id, provenance chains, and status. Errors MUST be logged with full stack traces. The server MUST expose GraphIndex statistics (total_nodes, total_edges, load_time_ms, memory_estimate_mb) for health monitoring.

- **Reliability**: Tools MUST implement retry logic with exponential backoff for transient failures. The GraphRAG MCP client implements 2 retries with 1s and 2s backoffs. Timeout configuration MUST be unified across all query paths (currently 120 seconds). Success rates MUST be tracked and failures investigated when success rate drops below 98%.

### Data & Storage

- **Graph Storage Format**: Commune graphs MUST be stored as GraphML files with standardized attributes: entity_name, entity_type, description, source_id (chunk references separated by `<SEP>`). Edges MUST include relationship_type or type attribute. Chunks MUST be stored in kv_store_text_chunks.json with content, tokens, chunk_order_index, full_doc_id, commune fields.

- **Pre-Computed Indices**: The GraphIndex MUST load all commune data at server startup into adjacency lists, entity metadata dictionaries, name indices, and chunk metadata stores. Lazy loading is prohibited—all data MUST be in-memory before accepting queries. Initialization time MUST be logged for capacity planning.

- **Memory Management**: Memory usage MUST scale linearly with corpus size. Current estimate: ~200 bytes/entity + ~50 bytes/edge + ~1500 bytes/chunk. The GraphIndex._estimate_memory_mb() method MUST be updated if data structures change. Memory estimates MUST be exposed via the /stats endpoint or logged at startup.

### Query & Retrieval

- **Dual-Strategy Retrieval**: Cross-commune queries MUST combine community-based keyword selection AND global entity search to achieve corpus-wide coverage. Commune filtering MUST be disabled for cross-commune expansion (pass None to expand_via_index). This ensures 92.7% coverage vs. 16% with single-strategy retrieval.

- **Weighted Traversal**: Graph expansion MUST use Dijkstra's algorithm with relationship type weights (RELATIONSHIP_WEIGHTS dict in graph_index.py). Higher weights prioritize semantic relationships (CONCERNE: 1.0, HAS_SOURCE: 0.9) over structural relationships (APPARTIENT_A: 0.3, RELATED_TO: 0.1). Entity type priorities MUST favor COMMUNE (10), CONCEPT (8), CHUNK (6) in traversal ordering.

- **Rate Limiting**: Multi-commune parallel queries MUST use asyncio.Semaphore to limit concurrent OpenAI API calls (MAX_CONCURRENT=5). This prevents HTTP 429 rate limit errors when querying all 50 communes simultaneously.

## Development Workflow

### Feature Development (Speckit Integration)

All feature development MUST follow the spec-driven workflow:

1. **Specification** (`/speckit.specify`): User stories MUST be prioritized (P1, P2, P3) and independently testable. Each story MUST define acceptance scenarios and independent test criteria.

2. **Planning** (`/speckit.plan`): Implementation plans MUST pass Constitutional Check gate before Phase 0 research. Plans MUST define project structure, technical context, and complexity justifications for any constitutional violations.

3. **Task Generation** (`/speckit.tasks`): Tasks MUST be organized by user story to enable independent implementation. Foundational phase tasks MUST be identified as blocking prerequisites. Parallel opportunities MUST be marked with [P] tags.

4. **Implementation** (`/speckit.implement`): Features MUST be implemented incrementally by user story priority (P1 → P2 → P3). Each story MUST be independently testable before moving to the next.

### Testing & Validation

- **Contract Tests**: When features add or modify MCP tools, contract tests MUST verify parameter schemas, response formats, and error handling. Tests MUST use the MCP Inspector or equivalent tooling.

- **Integration Tests**: Multi-hop graph traversal MUST be integration tested with known entity seeds and expected neighbor sets. Chunk retrieval MUST be tested for entities with known source_ids.

- **Performance Tests**: Optimization PRs MUST include before/after latency benchmarks. Query latency MUST be measured from request dispatch to response completion using perf_counter. Statistical significance MUST be demonstrated for claimed improvements (e.g., Welch's t-test for latency comparisons).

### Documentation Standards

- **Troubleshooting Entries**: Bug fixes that reveal architectural insights MUST add troubleshooting.md entries. Entries MUST follow the template: Problem → Cause → Solution → Impact → Date fixed. Code references MUST include file paths and line numbers.

- **Performance Metrics**: Optimization claims MUST include quantified improvements (e.g., "50x speedup", "25-30s → 0.5s"). Before/after measurements MUST use consistent methodology. Sample sizes MUST be reported for statistical claims.

- **API Documentation**: MCP tool descriptions MUST include: Purpose, Parameters with types and descriptions, Return value format, Error conditions, Example invocations. Tools MUST use Annotated[type, Field(description="...")] for self-documenting schemas.

## Governance

### Amendment Process

Amendments to this constitution require:

1. **Proposal**: Document proposed change with rationale and impact analysis
2. **Validation**: Demonstrate that change does not break core principles I-III (graph-first, no orphans, provenance)
3. **Template Sync**: Update all dependent templates (spec, plan, tasks, commands) to reflect constitutional changes
4. **Version Bump**: Increment version according to semantic versioning (MAJOR for principle removals, MINOR for additions, PATCH for clarifications)

### Compliance & Review

- All feature PRs MUST pass Constitutional Check in plan.md before Phase 0 research begins
- Complexity violations MUST be documented in the Complexity Tracking table with justification
- Performance regressions MUST be caught in integration testing and investigated before merge
- OPIK evaluation results MUST be reviewed for semantic quality regressions (meaning_match, hallucination)

### Version Control

**Version**: 1.0.0 | **Ratified**: 2026-01-06 | **Last Amended**: 2026-01-06
