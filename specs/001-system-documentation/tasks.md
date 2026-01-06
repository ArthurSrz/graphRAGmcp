# Tasks: Comprehensive System Documentation

**Input**: Design documents from `/specs/001-system-documentation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/doc-validation-schema.json, quickstart.md

**Tests**: This feature does NOT require test tasks - validation is achieved through the documentation validation script itself (scripts/validate-docs.py)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each documentation set.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Documentation lives in `docs/` at repository root following audience-based structure:
- `docs/getting-started/` - Developer onboarding (US1)
- `docs/api-reference/` - API specifications (US2)
- `docs/integration/` - Client configurations (US2)
- `docs/operations/` - Ops procedures (US3)
- `docs/research-guide/` - End-user guides (US4)
- `docs/architecture/` - Deep technical dives (all audiences)

---

## Phase 1: Setup (Documentation Infrastructure)

**Purpose**: Initialize documentation structure and validation tooling

- [ ] T001 Create docs/ directory structure per plan.md (getting-started/, api-reference/, integration/, operations/, research-guide/, architecture/)
- [ ] T002 Install MkDocs with Material theme dependencies (pip install mkdocs mkdocs-material pymdown-extensions)
- [ ] T003 [P] Create mkdocs.yml configuration with navigation structure for 4 user personas
- [ ] T004 [P] Create docs/index.md landing page with audience navigation (developer/integrator/operator/researcher pathways)
- [ ] T005 [P] Copy .specify/memory/constitution.md to docs/constitution.md or create symlink

---

## Phase 2: Foundational (Documentation Validation Framework)

**Purpose**: Core validation infrastructure that enables code example testing across ALL documentation

**⚠️ CRITICAL**: This validation framework must be complete before documentation can be validated per SC-007 (95% success rate)

- [ ] T006 Create scripts/ directory for validation tooling
- [ ] T007 Implement scripts/validate-docs.py with mistune Markdown parser for extracting code blocks
- [ ] T008 Add code example extraction logic in validate-docs.py (detect language, purpose, dependencies from comments)
- [ ] T009 Implement Python code execution in validate-docs.py with subprocess management
- [ ] T010 [P] Implement Bash/shell code execution in validate-docs.py with timeout handling
- [ ] T011 [P] Implement JSON/YAML validation in validate-docs.py using jsonschema
- [ ] T012 Add dependency checking in validate-docs.py (ENV variables, PKG imports, STATE requirements)
- [ ] T013 Add expected output comparison in validate-docs.py with pattern matching
- [ ] T014 Implement frontmatter YAML validation against contracts/doc-validation-schema.json
- [ ] T015 Add validation reporting with pass/fail statistics and error details
- [ ] T016 Create .github/workflows/validate-docs.yml for CI/CD integration per research.md

**Checkpoint**: Validation framework ready - documentation files can now be created with automated quality checks

---

## Phase 3: User Story 1 - Developer Onboarding (Priority: P1) 🎯 MVP

**Goal**: Enable new developers to understand architecture, set up dev environment, and make first contribution within 2 hours

**Independent Test**: New developer with Python experience can follow docs to run server locally, explain architecture, and locate code for adding new MCP tool without >2 hours mentorship

### Implementation for User Story 1

- [ ] T017 [P] [US1] Create docs/getting-started/overview.md with system purpose, key components (GraphRAG, MCP, FastMCP), and data flow diagrams
- [ ] T018 [P] [US1] Create docs/getting-started/architecture.md documenting graph-first design, MCP integration, dual-strategy retrieval, weighted traversal
- [ ] T019 [P] [US1] Create docs/getting-started/setup.md with development environment setup (Python 3.11+, dependencies, dataset path configuration)
- [ ] T020 [P] [US1] Create docs/getting-started/first-contribution.md with guide for adding new MCP tool following FastMCP patterns
- [ ] T021 [US1] Add code examples to setup.md (pip install, environment variables, server startup commands) with REQUIRES annotations
- [ ] T022 [US1] Add code examples to first-contribution.md (FastMCP tool decorator, parameter validation, response format)
- [ ] T023 [US1] Add cross-references in getting-started/ docs to architecture/ deep dives (graph-index.md, mcp-protocol.md)
- [ ] T024 [US1] Validate all User Story 1 documentation using scripts/validate-docs.py (target: 95% success rate per SC-007)

**Checkpoint**: Developer onboarding documentation complete and validated - supports SC-001 (2 hour onboarding time)

---

## Phase 4: User Story 2 - API Consumer Integration (Priority: P2)

**Goal**: Enable external developers to integrate GraphRAG MCP server into LLM applications with clear API documentation

**Independent Test**: External developer with no prior knowledge can configure MCP client and execute 3+ query types using only provided documentation

### Implementation for User Story 2

#### API Reference Documentation

- [ ] T025 [P] [US2] Create docs/api-reference/mcp-tools.md with overview of all 5 MCP tools and when to use each
- [ ] T026 [P] [US2] Create docs/api-reference/grand_debat_list_communes.md documenting parameters, return format, error conditions, usage examples
- [ ] T027 [P] [US2] Create docs/api-reference/grand_debat_query.md documenting query modes (local/global), parameters, provenance response format
- [ ] T028 [P] [US2] Create docs/api-reference/grand_debat_search_entities.md documenting entity search parameters, entity types, relationship filtering
- [ ] T029 [P] [US2] Create docs/api-reference/grand_debat_get_communities.md documenting community exploration, Louvain algorithm, theme extraction
- [ ] T030 [P] [US2] Create docs/api-reference/grand_debat_get_contributions.md documenting contribution retrieval, commune filtering, text chunk access
- [ ] T031 [P] [US2] Create docs/api-reference/parameters.md documenting common parameter types (commune_ids, query strings, mode enum, limit/offset)
- [ ] T032 [P] [US2] Create docs/api-reference/responses.md documenting response schemas, provenance chains (chunk→entity→response), source quote format
- [ ] T033 [P] [US2] Create docs/api-reference/errors.md documenting error codes, common error patterns, troubleshooting steps per tool

#### Client Integration Guides

- [ ] T034 [P] [US2] Create docs/integration/claude-desktop.md with MCP configuration JSON example, environment variables, verification steps
- [ ] T035 [P] [US2] Create docs/integration/cline-vscode.md with Cline MCP settings, workspace configuration, tool visibility checks
- [ ] T036 [P] [US2] Create docs/integration/dust-tt.md with Dust.tt connector configuration, API endpoint setup, authentication
- [ ] T037 [P] [US2] Create docs/integration/custom-client.md with MCP protocol implementation guide, JSON-RPC 2.0 examples, session management

#### Code Examples and Validation

- [ ] T038 [US2] Add Python code examples to all api-reference/ docs using mcp ClientSession with realistic queries
- [ ] T039 [US2] Add Bash/curl examples to integration/ docs with MCP JSON-RPC payloads and expected responses
- [ ] T040 [US2] Add JSON configuration examples to integration/ docs with proper REQUIRES: ENV annotations
- [ ] T041 [US2] Validate all User Story 2 documentation using scripts/validate-docs.py (target: 95% success per SC-007)

**Checkpoint**: API integration documentation complete - supports SC-002 (90% first-attempt success), SC-003 (85% valid queries), SC-009 (zero undocumented tools)

---

## Phase 5: User Story 3 - Operations & Maintenance (Priority: P3)

**Goal**: Enable DevOps engineers to deploy, monitor, and maintain GraphRAG MCP server in production

**Independent Test**: Ops engineer can deploy to new environment, configure monitoring, and resolve simulated performance issue using only operational documentation

### Implementation for User Story 3

- [ ] T042 [P] [US3] Create docs/operations/deployment.md with Railway deployment guide (railway.json, environment variables, health checks)
- [ ] T043 [P] [US3] Add Cloud Run deployment section to docs/operations/deployment.md (gcloud commands, service configuration, proxy setup)
- [ ] T044 [P] [US3] Create docs/operations/monitoring.md documenting OPIK integration, metrics export (latency, success rate, memory), dashboard setup
- [ ] T045 [P] [US3] Create docs/operations/performance.md with benchmark results from experimental-design-rag-comparison.md (local mode: 520ms mean, global mode: 890ms p95)
- [ ] T046 [P] [US3] Add performance tuning guidance to docs/operations/performance.md (graph loading optimization, LLM timeout configuration, concurrent request limits)
- [ ] T047 [P] [US3] Create docs/operations/troubleshooting.md expanding root troubleshooting.md with categorized error patterns (rate limits, session failures, timeout errors)
- [ ] T048 [P] [US3] Create docs/operations/incident-response.md with runbooks for common incidents (high latency, OOM errors, API quota exhaustion)
- [ ] T049 [US3] Add deployment verification code examples (health check curl commands, metric query examples, log parsing scripts)
- [ ] T050 [US3] Add troubleshooting code examples (diagnostic queries, log analysis commands, configuration validation scripts)
- [ ] T051 [US3] Validate all User Story 3 documentation using scripts/validate-docs.py (target: 95% success per SC-007)

**Checkpoint**: Operations documentation complete - supports SC-004 (30 min incident resolution), SC-005 (<2 week doc lag)

---

## Phase 6: User Story 4 - Civic Research & Analysis (Priority: P4)

**Goal**: Enable civic researchers to query Grand Débat National dataset and interpret results with provenance

**Independent Test**: Non-technical researcher can formulate research questions, construct queries, and interpret results to answer research questions

### Implementation for User Story 4

- [ ] T052 [P] [US4] Create docs/research-guide/dataset.md documenting Grand Débat National source, 50 commune coverage, entity counts (1847 concepts, 234 themes), collection methodology
- [ ] T053 [P] [US4] Create docs/research-guide/query-modes.md explaining local mode (specific facts within communes) vs global mode (thematic overview across communes)
- [ ] T054 [P] [US4] Create docs/research-guide/examples.md with 10+ research query examples (taxation concerns, public services, democratic participation, environmental topics)
- [ ] T055 [P] [US4] Create docs/research-guide/interpreting-results.md documenting provenance chains, source quote verification, answer quality assessment
- [ ] T056 [US4] Add example queries to research-guide/examples.md with expected result patterns and interpretation notes
- [ ] T057 [US4] Add provenance navigation examples to interpreting-results.md (chunk→entity→response tracing)
- [ ] T058 [US4] Validate all User Story 4 documentation using scripts/validate-docs.py (target: 95% success per SC-007)

**Checkpoint**: Research guide documentation complete - supports SC-008 (effective queries within 3 attempts), SC-010 (4.0/5.0 usefulness rating)

---

## Phase 7: Architecture Deep Dives (Cross-Cutting)

**Purpose**: Detailed technical documentation serving all audiences with deep dives into system internals

- [ ] T059 [P] Create docs/architecture/graph-index.md documenting GraphIndex implementation, adjacency list pre-computation, entity/relationship storage
- [ ] T060 [P] Create docs/architecture/mcp-protocol.md documenting MCP integration details, JSON-RPC 2.0 message flow, tool registration, session lifecycle
- [ ] T061 [P] Create docs/architecture/dual-strategy-retrieval.md documenting cross-commune query optimization, community-based vs global entity search strategies
- [ ] T062 [P] Create docs/architecture/weighted-traversal.md documenting Dijkstra's algorithm application, relationship type priorities, entity type priorities
- [ ] T063 [P] Create docs/architecture/provenance.md documenting chunk→entity→response chains, source attribution, interpretability guarantees
- [ ] T064 Add technical diagrams to architecture/ docs (Mermaid diagrams for graph traversal, MCP message flow, dual-strategy decision tree)
- [ ] T065 Add code references to architecture/ docs linking to actual implementation (server.py line numbers, graph_index.py functions)
- [ ] T066 Validate all architecture documentation using scripts/validate-docs.py

**Checkpoint**: Architecture documentation complete - provides depth for advanced users across all personas

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements affecting multiple documentation sections and ensuring quality standards

- [ ] T067 [P] Create docs/contributing.md with documentation contribution guidelines, branching strategy, PR template per quickstart.md
- [ ] T068 [P] Copy quickstart.md content to docs/contributing.md or create symlink for contributor access
- [ ] T069 [P] Add "See Also" cross-references across all documentation using related_artifacts from frontmatter metadata
- [ ] T070 [P] Add search keywords to frontmatter metadata for improved discoverability (MCP, GraphRAG, Grand Débat, commune, etc.)
- [ ] T071 Review all code examples for security issues (no hardcoded API keys, proper environment variable usage, input validation examples)
- [ ] T072 Verify all file paths in code examples use environment variables not absolute paths per quickstart.md guidelines
- [ ] T073 Run full documentation validation: python scripts/validate-docs.py (must achieve ≥95% success rate per SC-007)
- [ ] T074 Build MkDocs site locally: mkdocs build (verify no broken links, navigation complete, search index generated)
- [ ] T075 Review MkDocs site preview: mkdocs serve (verify rendering, formatting, code syntax highlighting)
- [ ] T076 Update all frontmatter last_updated and validation_date fields to current date
- [ ] T077 Generate documentation metrics report (total artifacts, code examples count, validation success rate, audience coverage)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all documentation writing
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories CAN proceed in parallel (different doc files, no cross-dependencies)
  - OR sequentially in priority order: US1 (P1) → US2 (P2) → US3 (P3) → US4 (P4)
- **Architecture (Phase 7)**: Can proceed in parallel with user stories (independent deep dives)
- **Polish (Phase 8)**: Depends on all documentation being complete

### User Story Dependencies

- **User Story 1 (P1) - Developer Onboarding**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2) - API Integration**: Can start after Foundational (Phase 2) - References US1 architecture docs but independently testable
- **User Story 3 (P3) - Operations**: Can start after Foundational (Phase 2) - References performance benchmarks but independently testable
- **User Story 4 (P4) - Research Guide**: Can start after Foundational (Phase 2) - References dataset description but independently testable

### Within Each User Story

- Documentation files marked [P] can be written in parallel (different files)
- Code examples added after documentation structure complete
- Validation runs after all documentation for that story is written
- Story complete before moving to next priority (or in parallel if staffed)

### Parallel Opportunities

**Within Setup (Phase 1)**:
- T003 (mkdocs.yml), T004 (index.md), T005 (constitution.md) can all run in parallel

**Within Foundational (Phase 2)**:
- T010 (Bash execution), T011 (JSON validation) can run in parallel after T007-T009

**Across User Stories (Phases 3-6)**:
- All 4 user stories can be worked on in parallel by different team members
- Within each story, all documentation files marked [P] can be written in parallel

**Architecture Phase (Phase 7)**:
- All 5 architecture docs (T059-T063) can be written in parallel

**Polish Phase (Phase 8)**:
- T067-T070 (contributing guide, cross-refs, keywords, security) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all User Story 1 documentation files together:
Task: "Create docs/getting-started/overview.md with system purpose, key components, data flow"
Task: "Create docs/getting-started/architecture.md documenting graph-first design, MCP integration"
Task: "Create docs/getting-started/setup.md with dev environment setup"
Task: "Create docs/getting-started/first-contribution.md with MCP tool addition guide"

# After structure complete, add code examples sequentially:
Task: "Add code examples to setup.md"
Task: "Add code examples to first-contribution.md"

# Finally validate:
Task: "Validate all User Story 1 documentation"
```

---

## Parallel Example: User Story 2 - API Reference

```bash
# Launch all API reference docs together:
Task: "Create docs/api-reference/mcp-tools.md"
Task: "Create docs/api-reference/grand_debat_list_communes.md"
Task: "Create docs/api-reference/grand_debat_query.md"
Task: "Create docs/api-reference/grand_debat_search_entities.md"
Task: "Create docs/api-reference/grand_debat_get_communities.md"
Task: "Create docs/api-reference/grand_debat_get_contributions.md"
Task: "Create docs/api-reference/parameters.md"
Task: "Create docs/api-reference/responses.md"
Task: "Create docs/api-reference/errors.md"

# Launch all integration guides together:
Task: "Create docs/integration/claude-desktop.md"
Task: "Create docs/integration/cline-vscode.md"
Task: "Create docs/integration/dust-tt.md"
Task: "Create docs/integration/custom-client.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005) - 1 hour
2. Complete Phase 2: Foundational (T006-T016) - 2-3 days (validation framework)
3. Complete Phase 3: User Story 1 (T017-T024) - 1-2 days
4. **STOP and VALIDATE**: Test with actual new developer onboarding
5. Deploy MkDocs site if ready

**Total MVP Time**: ~4-5 days for developer onboarding documentation with validation

### Incremental Delivery

1. Complete Setup + Foundational → Validation framework ready (~3 days)
2. Add User Story 1 → Test independently → Deploy/Demo (MVP! ~1-2 days)
3. Add User Story 2 → Test independently → Deploy/Demo (~2-3 days - most docs)
4. Add User Story 3 → Test independently → Deploy/Demo (~1-2 days)
5. Add User Story 4 → Test independently → Deploy/Demo (~1 day)
6. Add Architecture deep dives → Deploy/Demo (~2 days)
7. Polish and cross-cutting concerns → Final release (~1 day)

**Total Feature Time**: ~11-14 days for complete comprehensive documentation

### Parallel Team Strategy

With 3 contributors after Foundational phase complete:

1. **Contributor 1**: User Story 1 (Developer Onboarding) - 1-2 days
2. **Contributor 2**: User Story 2 (API Integration) - 2-3 days
3. **Contributor 3**: User Story 3 (Operations) - 1-2 days

Then:
- Contributor 1 adds User Story 4 (Research) - 1 day
- Contributor 2 adds Architecture docs - 2 days
- Contributor 3 handles Polish phase - 1 day

**Parallel Total Time**: ~5-6 days (vs 11-14 days sequential)

---

## Success Metrics Tracking

**Per Success Criteria from spec.md**:

- **SC-001** (2 hour onboarding): Track with User Story 1 validation - time new developer from docs to first PR
- **SC-002** (90% setup success): Track with User Story 2 integration guides - monitor setup error tickets
- **SC-003** (85% valid queries): Track with User Story 2 API reference - monitor validation errors in logs
- **SC-004** (30 min incident resolution): Track with User Story 3 troubleshooting - incident resolution time metrics
- **SC-005** (<2 week doc lag): Track with validation_date in frontmatter - automated staleness detection
- **SC-006** (60% support reduction): Track support ticket categorization before/after documentation release
- **SC-007** (95% code example success): Track with scripts/validate-docs.py - automated validation reports
- **SC-008** (3 attempts for effective queries): Track with User Story 4 examples - researcher query refinement counts
- **SC-009** (zero undocumented tools): Track with User Story 2 API coverage - verify all 5 MCP tools documented
- **SC-010** (4.0/5.0 usefulness): Track with documentation feedback survey after release

---

## Notes

- [P] tasks = different files, no dependencies - safe to run in parallel
- [Story] label maps task to specific user story for traceability and independent testing
- Each user story should be independently completable and testable
- Commit after each documentation file or logical group
- Stop at any checkpoint to validate story independently
- Validation framework (Phase 2) is critical path - blocks all documentation work
- Total task count: 77 tasks organized into 8 phases
- Parallelization reduces timeline from ~14 days to ~6 days with 3 contributors
