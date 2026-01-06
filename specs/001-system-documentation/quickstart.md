# Quickstart: Contributing to Documentation

**Audience**: Contributors to GraphRAG MCP Server documentation
**Last Updated**: 2026-01-06
**Prerequisites**: Git, Python 3.11+, familiarity with Markdown

## Purpose

This guide enables contributors to add or update documentation following project standards. By the end, you'll be able to create documentation that passes automated validation and serves your target audience effectively.

## 1. Setup

### Clone and Install

```bash
# Clone repository
git clone https://github.com/ArthurSrz/graphRAGmcp.git
cd graphRAGmcp

# Install documentation dependencies
pip install mkdocs mkdocs-material pymdown-extensions

# Install validation dependencies
pip install pytest pytest-md pyyaml jsonschema
```

### Run Local Preview

```bash
# Start MkDocs development server
mkdocs serve

# Documentation available at http://127.0.0.1:8000
# Auto-reloads when you save changes
```

### Verify Installation

```bash
# Test validation script
python scripts/validate-docs.py --help

# Expected output: Usage instructions for doc validation tool
```

## 2. File Placement

Documentation is organized by target audience in `docs/` directory:

| Audience | Directory | Purpose |
|----------|-----------|---------|
| **Developers** | `docs/getting-started/` | Onboarding, architecture, setup guides |
| **Integrators** | `docs/api-reference/`, `docs/integration/` | MCP tools, client configuration |
| **Operators** | `docs/operations/` | Deployment, monitoring, troubleshooting |
| **Researchers** | `docs/research-guide/` | Dataset description, query examples |
| **All** | `docs/architecture/` | Deep technical dives (graph algorithms, protocols) |

### Choosing the Right Location

**Ask yourself**: *Who needs this information first?*

- "How do I set up my dev environment?" → `getting-started/setup.md`
- "What parameters does grand_debat_query accept?" → `api-reference/grand_debat_query.md`
- "How do I deploy to Railway?" → `operations/deployment.md`
- "How do I query taxation topics?" → `research-guide/examples.md`
- "How does weighted traversal work?" → `architecture/weighted-traversal.md`

## 3. Writing Guidelines

### Frontmatter (Required)

Every `.md` file MUST include YAML frontmatter with metadata:

```markdown
---
title: "Your Documentation Title"
audience: developer  # or integrator, operator, researcher
content_type: procedural  # or conceptual, reference, tutorial
maintenance_status: current
last_updated: 2026-01-06
related_artifacts:
  - path/to/related-doc.md
validation_status: true
validation_date: 2026-01-06
---

# Your Documentation Title

[Content starts here...]
```

**Field Descriptions**:
- `audience`: Primary reader (affects navigation placement)
- `content_type`:
  - **conceptual**: Explains ideas (e.g., "What is GraphRAG?")
  - **procedural**: Step-by-step instructions (e.g., "How to deploy")
  - **reference**: Specifications (e.g., "MCP tool parameters")
  - **tutorial**: Learning-oriented walkthrough (e.g., "Your first query")
- `maintenance_status`: Set to `current` for new docs
- `related_artifacts`: Cross-references for "See Also" sections

### Markdown Conventions

**Headings**:
- Use ATX-style (`#` prefix), not Setext (`===` underline)
- One H1 (`#`) per file, matching frontmatter title
- Hierarchical structure: H2 (`##`) for sections, H3 (`###`) for subsections

**Code Blocks**:
- Always specify language for syntax highlighting
- Include comments explaining non-obvious steps
- Use realistic examples (actual MCP tool names, real parameters)

**Good Example**:
````markdown
```python
# Import FastMCP server instance
from server import mcp

# Query 50 communes in local mode
result = mcp.call_tool(
    "grand_debat_query",
    {
        "query": "What are citizens' concerns about taxation?",
        "mode": "local",  # Search within specific commune contexts
        "commune_ids": ["17001", "17002"]  # Charente-Maritime communes
    }
)
```
````

**Bad Example** (missing language, no context):
````markdown
```
result = mcp.call_tool("grand_debat_query", {...})
```
````

**Links**:
- Use relative paths for internal links: `[Architecture](../architecture/graph-index.md)`
- Use absolute URLs for external links: `[MCP Spec](https://modelcontextprotocol.io/spec)`

## 4. Code Examples: Testable Format

**Critical Requirement**: Code examples MUST be testable against the live system.

### Marking Dependencies

Use specially-formatted comments to declare dependencies:

**Python Example**:
```python
# REQUIRES: ENV:GRAND_DEBAT_DATA_PATH
# REQUIRES: ENV:OPENAI_API_KEY
# REQUIRES: PKG:mcp
# REQUIRES: STATE:GraphRAG server running on localhost:8000

from mcp import ClientSession

async with ClientSession(...) as session:
    # Example continues...
```

**Bash Example**:
```bash
# REQUIRES: ENV:MCP_SERVER_URL
# REQUIRES: STATE:Server deployed and accessible

curl -X POST $MCP_SERVER_URL/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "grand_debat_list_communes"}'
```

### Expected Output (Optional but Recommended)

For deterministic examples, include expected output for validation:

```python
# EXPECTED_OUTPUT: {"communes": ["17001", "17002", ...], "total": 50}

result = list_communes()
print(result)
```

### Non-Executable Examples

If an example is illustrative only (not meant to run), mark it:

```python
# NON_EXECUTABLE: Configuration template example only

{
  "mcpServers": {
    "graphrag": {
      "command": "python",
      "args": ["-m", "server"],
      "env": {
        "OPENAI_API_KEY": "your-key-here"  # Replace with actual key
      }
    }
  }
}
```

## 5. Validation

### Before Committing

Run validation locally to catch issues early:

```bash
# Validate all documentation
python scripts/validate-docs.py

# Validate specific file
python scripts/validate-docs.py docs/getting-started/setup.md

# Dry-run without executing code
python scripts/validate-docs.py --dry-run
```

**Expected Output** (passing):
```
✓ docs/getting-started/setup.md
  - Frontmatter valid
  - 3 code examples found
  - 3/3 examples passed validation

✓ docs/api-reference/mcp-tools.md
  - Frontmatter valid
  - 5 code examples found
  - 5/5 examples passed validation

Overall: 8/8 examples passed (100%)
```

**Expected Output** (failing):
```
✗ docs/integration/claude-desktop.md
  - Frontmatter valid
  - 2 code examples found
  - 1/2 examples passed validation

  FAILED: integration/claude-desktop.md#1
  Error: ENV:GRAND_DEBAT_DATA_PATH not set
  Fix: Set required environment variable or mark as NON_EXECUTABLE

Overall: 7/8 examples passed (87.5% - below 95% threshold)
```

### Fixing Validation Errors

**Common Issues**:

| Error | Cause | Fix |
|-------|-------|-----|
| `ENV:X not set` | Missing environment variable | Set variable or mark `NON_EXECUTABLE` |
| `Syntax error in line N` | Invalid Python/Bash syntax | Fix code syntax |
| `Output mismatch` | Actual output ≠ expected | Update `EXPECTED_OUTPUT` or fix code |
| `Import error: module X` | Missing package | Add to `REQUIRES: PKG:X` or install |

## 6. Contribution Workflow

### Creating a Feature Branch

```bash
# Ensure you're on main
git checkout main
git pull origin main

# Create feature branch (use your GitHub username)
git checkout -b docs/your-username/descriptive-name

# Example: docs/asmith/add-deployment-guide
```

### Making Changes

1. Create or edit Markdown files in appropriate `docs/` subdirectory
2. Add frontmatter metadata
3. Write content following guidelines above
4. Run validation: `python scripts/validate-docs.py`
5. Preview locally: `mkdocs serve`

### Committing

```bash
# Stage changes
git add docs/

# Commit with descriptive message
git commit -m "docs: add Railway deployment guide for operators

- Created operations/deployment-railway.md with step-by-step setup
- Includes environment variable configuration and health checks
- All code examples validated (3/3 passing)"

# Push to your fork
git push origin docs/your-username/descriptive-name
```

### Pull Request

1. Open PR on GitHub from your branch to `main`
2. Title: `docs: [brief description]`
3. Description should include:
   - **Purpose**: What documentation this adds/improves
   - **Audience**: Who benefits from this change
   - **Validation**: Confirmation that `validate-docs.py` passes
   - **Preview**: Screenshot or description of how it looks in MkDocs

**Example PR Description**:
```markdown
## Purpose
Adds comprehensive Railway deployment guide for operators managing production deployments.

## Audience
DevOps engineers deploying GraphRAG MCP server to Railway cloud platform.

## Validation
- ✅ All 5 code examples pass validation
- ✅ Frontmatter metadata complete
- ✅ Local MkDocs preview renders correctly

## Preview
New file appears under "Operations" section in docs navigation. Includes:
- Environment variable setup
- Railway.app configuration
- Health check verification
- Troubleshooting common deployment issues
```

### Review Process

Documentation PRs require:
1. ✅ Passing validation (`validate-docs.py` returns 95%+ success)
2. ✅ Peer review (at least 1 approval)
3. ✅ Appropriate audience/content_type metadata
4. ✅ Cross-references to related docs where applicable

## 7. Documentation Standards Summary

**DO**:
- ✅ Include complete frontmatter metadata
- ✅ Place docs in audience-appropriate directory
- ✅ Specify language for all code blocks
- ✅ Declare dependencies for executable examples
- ✅ Run validation before committing
- ✅ Use relative links for internal cross-references
- ✅ Keep paragraphs focused (3-5 sentences max)

**DON'T**:
- ❌ Skip frontmatter (validation will fail)
- ❌ Use bare code blocks without language (breaks syntax highlighting)
- ❌ Include untested examples without `NON_EXECUTABLE` marker
- ❌ Hard-code absolute file paths (use environment variables)
- ❌ Create orphan pages (always link from navigation)
- ❌ Mix audiences in single document (split into separate files)

## 8. Getting Help

**Questions?**
- Check existing docs in your target directory for examples
- Review [Contributing Guide](../contributing.md) for general guidelines
- Ask in GitHub Discussions or open an issue with `documentation` label

**Found a bug in documentation?**
- File issue with steps to reproduce
- Include which doc file has the problem
- Suggest a fix if you have one

**Want to propose major documentation restructuring?**
- Open GitHub Discussion first (avoid large PRs without alignment)
- Explain rationale and expected impact
- Wait for maintainer feedback before implementing

---

**Next Steps**: Once you've contributed your first documentation PR, consider helping with:
- Translating guides to French for researcher audience
- Adding more query examples to `research-guide/examples.md`
- Improving search discoverability with better keywords
- Creating tutorial-style walkthroughs for common workflows
