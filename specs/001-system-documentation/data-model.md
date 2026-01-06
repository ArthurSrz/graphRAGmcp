# Data Model: Comprehensive System Documentation

**Feature**: 001-system-documentation
**Created**: 2026-01-06
**Purpose**: Define entities and relationships for documentation artifacts, code examples, configurations, and metadata

## Overview

This data model describes the structure of documentation artifacts and their metadata. Unlike typical application data models, this represents documentation-as-data, enabling automated validation, version tracking, and quality assurance.

## Core Entities

### Documentation Artifact

Represents a cohesive unit of documentation (guide, reference, tutorial).

**Attributes**:
- `id` (string, required): Unique identifier, file path relative to `docs/` (e.g., "getting-started/architecture.md")
- `title` (string, required): Human-readable title displayed in navigation and search results
- `target_audience` (enum, required): Primary intended audience
  - Values: `developer`, `integrator`, `operator`, `researcher`
- `content_type` (enum, required): Type of documentation content
  - Values: `conceptual`, `procedural`, `reference`, `tutorial`
- `maintenance_status` (enum, required): Currency status
  - Values: `current`, `outdated`, `deprecated`
  - `current`: Validated against latest codebase within 2 weeks
  - `outdated`: Not validated within 2 weeks, may have drift
  - `deprecated`: Marked for removal, replaced by newer artifact
- `last_updated` (ISO date, required): Most recent content modification date
- `related_artifacts` (list of strings, optional): IDs of cross-referenced documentation
- `validation_status` (boolean, required): Whether code examples passed validation
- `validation_date` (ISO date, optional): When last validation occurred

**Relationships**:
- Contains 0..N `Code Example` entities (embedded code blocks)
- May reference 0..N other `Documentation Artifact` entities (cross-links)
- May reference 0..N `Configuration Template` entities (deployment/client configs)
- May reference 0..N `Performance Benchmark` entities (quantitative results)

**Example**:
```json
{
  "id": "getting-started/architecture.md",
  "title": "System Architecture Overview",
  "target_audience": "developer",
  "content_type": "conceptual",
  "maintenance_status": "current",
  "last_updated": "2026-01-06",
  "related_artifacts": [
    "architecture/graph-index.md",
    "architecture/mcp-protocol.md"
  ],
  "validation_status": true,
  "validation_date": "2026-01-06"
}
```

---

### Code Example

Represents an executable or copyable code snippet within documentation.

**Attributes**:
- `id` (string, required): Unique identifier, format: `{artifact_id}#{block_index}` (e.g., "api-reference/mcp-tools.md#3")
- `language` (string, required): Programming/markup language
  - Common values: `python`, `bash`, `json`, `yaml`, `javascript`
- `purpose` (string, required): What this example demonstrates (1-2 sentences)
- `tested` (boolean, required): Whether example has been executed against live system
- `dependencies` (list of strings, optional): Required environment variables, installed packages, or system state
  - Format: `ENV:VARIABLE_NAME` for env vars, `PKG:package-name` for packages, `STATE:description` for system state
- `expected_output` (string, optional): Expected result pattern or literal output for validation
- `validation_error` (string, optional): Most recent validation error if `tested=false`

**Relationships**:
- Belongs to exactly 1 `Documentation Artifact` (parent document)

**Example**:
```json
{
  "id": "integration/claude-desktop.md#1",
  "language": "json",
  "purpose": "Claude Desktop MCP server configuration for GraphRAG",
  "tested": true,
  "dependencies": [
    "ENV:GRAND_DEBAT_DATA_PATH",
    "ENV:OPENAI_API_KEY",
    "STATE:GraphRAG server deployed and accessible"
  ],
  "expected_output": null
}
```

---

### Configuration Template

Represents deployment or client configuration with required/optional settings.

**Attributes**:
- `id` (string, required): Unique identifier, format: `{platform}#{config_type}` (e.g., "railway#server-deployment")
- `platform` (enum, required): Deployment platform or client type
  - Values: `railway`, `cloud-run`, `claude-desktop`, `cline`, `dust-tt`, `custom`
- `required_variables` (map of string→string, required): Variable name to description mapping
  - Example: `{"OPENAI_API_KEY": "OpenAI API key for LLM calls", ...}`
- `optional_settings` (map of string→string, optional): Setting name to default value mapping
  - Example: `{"MAX_CONCURRENT": "5", "TIMEOUT_SECONDS": "120"}`
- `validation_criteria` (list of strings, required): Checks to confirm valid configuration
  - Example: `["Server responds to health check at /health", "MCP tools visible in client"]`

**Relationships**:
- Referenced by 1..N `Documentation Artifact` entities (deployment/integration guides)

**Example**:
```json
{
  "id": "claude-desktop#mcp-config",
  "platform": "claude-desktop",
  "required_variables": {
    "GRAND_DEBAT_DATA_PATH": "Absolute path to Grand Débat dataset directory",
    "OPENAI_API_KEY": "OpenAI API key for LLM inference"
  },
  "optional_settings": {
    "OPIK_API_KEY": "(Optional) Opik API key for query logging"
  },
  "validation_criteria": [
    "graphrag_mcp tools appear in Claude Desktop MCP tools list",
    "grand_debat_list_communes returns 50 communes when invoked"
  ]
}
```

---

### Performance Benchmark

Represents measured system characteristics with methodology and conditions.

**Attributes**:
- `id` (string, required): Unique identifier, format: `{metric_name}#{date}` (e.g., "query-latency#2026-01-06")
- `metric_name` (enum, required): Type of performance metric
  - Values: `latency`, `memory`, `throughput`, `success_rate`, `semantic_quality`
- `measurement_conditions` (string, required): Test environment and parameters description
  - Example: "Local mode queries on 50-commune dataset, OpenAI gpt-4o-mini, 5 concurrent requests"
- `observed_values` (map of string→number, required): Statistical measures
  - Keys: `mean`, `median`, `p50`, `p95`, `p99`, `min`, `max`, `stddev`, `sample_size`
- `date_measured` (ISO date, required): When benchmark was executed
- `methodology` (string, required): Reference to experimental design document or procedure
  - Example: "See docs/eval/experimental-design-rag-comparison.md section 3.2"
- `comparison_baseline` (string, optional): Reference to previous measurement for before/after comparison
  - Example: "query-latency#2025-12-15" (pre-optimization baseline)

**Relationships**:
- Referenced by 1..N `Documentation Artifact` entities (performance guides, troubleshooting docs)
- May reference 1 other `Performance Benchmark` (baseline for comparison)

**Example**:
```json
{
  "id": "query-latency-local#2026-01-06",
  "metric_name": "latency",
  "measurement_conditions": "Local mode queries, 50 communes, gpt-4o-mini, timeout=120s",
  "observed_values": {
    "mean": 520,
    "median": 480,
    "p95": 890,
    "p99": 1200,
    "min": 320,
    "max": 1450,
    "sample_size": 100
  },
  "date_measured": "2026-01-06",
  "methodology": "experimental-design-rag-comparison.md section 3.2 (A/B testing protocol)",
  "comparison_baseline": "query-latency-local#2025-11-20"
}
```

---

### Dataset Description

Represents metadata about indexed corpora available for querying.

**Attributes**:
- `id` (string, required): Unique identifier, dataset source name (e.g., "grand-debat-national")
- `source` (string, required): Official name of data source
  - Example: "Grand Débat National - Cahiers de Doléances"
- `coverage` (string, required): Scope description (geographic, temporal, thematic)
  - Example: "50 communes in Charente-Maritime department, collected January-March 2019"
- `entity_counts` (map of string→number, required): Count of entities by type
  - Keys: entity type names (COMMUNE, CONCEPT, THEME, CITIZEN_CONTRIBUTION, CHUNK)
- `relationship_counts` (map of string→number, required): Count of relationships by type
  - Keys: relationship type names (CONCERNE, HAS_SOURCE, APPARTIENT_A, RELATED_TO)
- `collection_date` (ISO date, required): When original data was collected
- `indexing_date` (ISO date, optional): When GraphRAG indexing was performed
- `data_license` (string, optional): License or terms of use for dataset

**Relationships**:
- Referenced by 1..N `Documentation Artifact` entities (dataset guides, research documentation)

**Example**:
```json
{
  "id": "grand-debat-national",
  "source": "Grand Débat National - Cahiers de Doléances",
  "coverage": "50 communes in Charente-Maritime (17), France, collected Q1 2019",
  "entity_counts": {
    "COMMUNE": 50,
    "CONCEPT": 1847,
    "THEME": 234,
    "CITIZEN_CONTRIBUTION": 3521,
    "CHUNK": 8942
  },
  "relationship_counts": {
    "CONCERNE": 5234,
    "HAS_SOURCE": 8942,
    "APPARTIENT_A": 3521,
    "RELATED_TO": 2156
  },
  "collection_date": "2019-03-15",
  "indexing_date": "2024-11-20",
  "data_license": "Open Government License (France)"
}
```

## Entity Relationships Diagram

```
Documentation Artifact (1) ──contains──> (N) Code Example
        │
        ├──references──> (N) Configuration Template
        │
        ├──references──> (N) Performance Benchmark
        │
        ├──references──> (N) Dataset Description
        │
        └──cross-references──> (N) Documentation Artifact

Performance Benchmark (1) ──compares-to──> (1) Performance Benchmark [baseline]
```

## Metadata Storage Strategy

**Implementation Approach**: Frontmatter YAML in Markdown files

Each documentation artifact (`.md` file) includes YAML frontmatter with metadata:

```markdown
---
title: "System Architecture Overview"
audience: developer
content_type: conceptual
maintenance_status: current
last_updated: 2026-01-06
related_artifacts:
  - architecture/graph-index.md
  - architecture/mcp-protocol.md
validation_status: true
validation_date: 2026-01-06
---

# System Architecture Overview

[Content begins here...]
```

**Rationale**: Frontmatter keeps metadata colocated with content, simplifies version control, and integrates naturally with MkDocs/static site generators.

## Validation Rules

### Documentation Artifact
- `id` MUST match actual file path in `docs/` directory
- `target_audience` and `content_type` MUST be populated for navigation generation
- `maintenance_status` MUST be set to `outdated` if `last_updated` is >14 days old and `validation_date` is null or >14 days old
- If `validation_status=false`, artifact MUST have at least one `Code Example` with `tested=false`

### Code Example
- `language` MUST be a valid language identifier for syntax highlighting
- If `tested=true`, `expected_output` SHOULD be populated for reproducibility
- If `tested=false`, `validation_error` SHOULD document the failure reason
- `dependencies` entries MUST follow `PREFIX:value` format (ENV/PKG/STATE)

### Configuration Template
- `required_variables` MUST NOT be empty (at minimum OPENAI_API_KEY required)
- `validation_criteria` MUST include at least one verifiable check
- Platform-specific configs MUST match actual client/deployment requirements

### Performance Benchmark
- `observed_values` MUST include at minimum: `mean`, `median`, `sample_size`
- `sample_size` MUST be ≥10 for statistical validity
- `methodology` MUST reference existing experimental design document or procedure
- If `comparison_baseline` is provided, baseline MUST exist and have same `metric_name`

### Dataset Description
- `entity_counts` and `relationship_counts` MUST reflect actual GraphIndex statistics
- `coverage` MUST specify geographic and temporal scope
- Counts MUST be updated when dataset is reindexed

## Evolution and Versioning

**Data Model Version**: 1.0.0

**Change Log**:
- 2026-01-06: Initial data model definition

**Future Additions** (not in v1.0.0):
- **Tutorial Progress Tracking**: Track user completion of tutorial steps
- **Search Analytics**: Log documentation search queries for improving content
- **Translation Status**: Track translation completeness for i18n artifacts
- **Dependency Graph**: Explicit dependency tracking between artifacts for impact analysis
