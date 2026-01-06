# Research: Code Example Validation in Markdown Documentation

**Date**: 2026-01-06
**Researcher**: Claude Code Agent
**Feature**: Comprehensive System Documentation (001)
**Focus**: Automated validation of code examples in Markdown against live GraphRAG MCP server

## Executive Summary

This research evaluates approaches for validating Python and Bash code examples in Markdown documentation against a live MCP server. The selected approach must achieve 95% success rate (SC-007) and integrate with CI/CD pipelines.

**Recommended Approach**: Custom pytest plugin with Markdown parser
**Rationale**: Maximum flexibility, MCP server-specific validation, existing pytest infrastructure
**Implementation Complexity**: Medium (3-5 days)
**Maintenance Burden**: Low (standard pytest patterns)

---

## Research Questions

### Q1: What tools exist for extracting and validating code from Markdown?

**Evaluated Options**:

1. **pytest-markdown-docs** (https://github.com/modal-labs/pytest-markdown-docs)
   - Extracts Python code blocks from Markdown
   - Runs them as pytest tests
   - Supports doctest-style assertions
   - **Pro**: Battle-tested, maintained by Modal Labs
   - **Con**: Limited to Python, no Bash/JSON/curl support
   - **Fit**: 60% - misses Bash examples critical for MCP testing

2. **pytest-doctestplus** (https://github.com/scientific-python/pytest-doctestplus)
   - Extended doctest with improved output comparison
   - Supports floating-point comparison, ellipsis matching
   - **Pro**: Rich assertion capabilities
   - **Con**: Requires doctest format (>>> prompt), not natural Markdown
   - **Fit**: 40% - poor developer experience for documentation

3. **codedown** (https://github.com/earldouglas/codedown)
   - Command-line tool to extract code blocks from Markdown
   - Outputs to separate files by language
   - **Pro**: Language-agnostic, simple extraction
   - **Con**: No validation logic, manual test writing required
   - **Fit**: 70% - good extraction, needs custom validation layer

4. **Custom pytest plugin** (built for this project)
   - Parse Markdown files with mistune/markdown-it
   - Extract fenced code blocks by language
   - Execute with appropriate interpreter (python/bash/curl)
   - Validate against expected patterns
   - **Pro**: Full control, MCP-specific logic, all languages
   - **Con**: Initial development effort
   - **Fit**: 95% - tailored to exact needs

**Decision**: Build custom pytest plugin using `mistune` for Markdown parsing.

**Rationale**:
- GraphRAG MCP documentation includes Python, Bash (curl commands), JSON, and YAML
- MCP server validation requires session management (initialize → call tools)
- Need to test against live server on localhost (not static output)
- Existing tools focus on single-language doctests, not multi-step MCP workflows
- Custom plugin enables context preservation across code blocks (session IDs)

---

### Q2: How to integrate validation into CI/CD pipeline?

**GitHub Actions Workflow**:

```yaml
name: Validate Documentation

on:
  push:
    paths:
      - 'docs/**/*.md'
      - 'server.py'
      - 'graph_index.py'
  pull_request:
    paths:
      - 'docs/**/*.md'

jobs:
  validate-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio mistune

      - name: Start MCP server
        run: |
          python server.py --stdio &
          sleep 5  # Wait for server initialization
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GRAND_DEBAT_DATA_PATH: ./law_data

      - name: Run documentation tests
        run: pytest tests/docs/ -v --tb=short

      - name: Generate validation report
        if: always()
        run: |
          pytest tests/docs/ --json-report --json-report-file=docs-validation.json

      - name: Upload validation report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: docs-validation-report
          path: docs-validation.json
```

**Integration Points**:
- Trigger on documentation changes (`docs/**/*.md`)
- Start MCP server before tests
- Generate JSON report for metrics tracking
- Upload artifacts for debugging failures

**CI/CD Decision**: GitHub Actions with pytest integration
**Rationale**: Repository already uses GitHub, pytest is Python standard, low friction

---

### Q3: What validation patterns work for different code types?

#### Pattern 1: Python MCP Client Examples

**Example in Markdown**:
````markdown
```python
from mcp.client import Client

# Initialize MCP client
client = Client("http://localhost:8080/mcp")
response = await client.call_tool(
    "grand_debat_list_communes",
    arguments={}
)
print(len(response["communes"]))  # Expected: 50
```
````

**Validation Approach**:
```python
def test_python_example(code_block, mcp_server):
    """Execute Python code and validate output/assertions."""
    # Extract expected value from comment
    expected_pattern = r"# Expected: (\d+)"
    expected = re.search(expected_pattern, code_block).group(1)

    # Execute code with MCP server context
    namespace = {"mcp_server": mcp_server}
    exec(code_block, namespace)

    # Validate assertions ran without error
    assert namespace.get("result") == int(expected)
```

#### Pattern 2: Bash/curl MCP Protocol Examples

**Example in Markdown**:
````markdown
```bash
# Initialize session
curl -X POST "http://localhost:8080/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "initialize", ...}'

# Response includes: "mcp-session-id" header
# Expected status: 200
```
````

**Validation Approach**:
```python
def test_bash_example(code_block, mcp_server_url):
    """Execute bash commands and validate HTTP responses."""
    # Parse expected outcomes from comments
    expected_status = extract_expected("status", code_block)
    expected_header = extract_expected("header", code_block)

    # Execute bash command
    result = subprocess.run(
        code_block,
        shell=True,
        capture_output=True,
        text=True
    )

    # Validate status code
    assert expected_status in result.stdout
```

#### Pattern 3: JSON Configuration Examples

**Example in Markdown**:
````markdown
```json
{
  "mcpServers": {
    "grand-debat": {
      "url": "https://graphragmcp-production.up.railway.app/mcp",
      "transport": "streamable-http"
    }
  }
}
```
````

**Validation Approach**:
```python
def test_json_example(code_block):
    """Validate JSON syntax and schema compliance."""
    # Parse JSON
    config = json.loads(code_block)

    # Validate against schema
    validate(config, MCP_CONFIG_SCHEMA)

    # Test URL accessibility (optional)
    response = requests.head(config["mcpServers"]["grand-debat"]["url"])
    assert response.status_code in [200, 405]  # 405 = HEAD not allowed but server alive
```

**Pattern Summary**:
- **Python**: Execute in isolated namespace, validate print/return values
- **Bash**: Execute with subprocess, parse stdout for expected patterns
- **JSON/YAML**: Validate syntax + schema, optionally test URLs
- **Multi-step workflows**: Preserve state across blocks (session IDs, variables)

---

### Q4: How to handle MCP session state across examples?

**Challenge**: MCP protocol requires initialization before tool calls. Documentation examples show multi-step workflows.

**Solution: Pytest Fixture with Session Management**

```python
import pytest
from mcp.client import Client

@pytest.fixture(scope="module")
async def mcp_session():
    """Persistent MCP session for documentation tests."""
    client = Client("http://localhost:8080/mcp")

    # Initialize session
    init_response = await client.initialize(
        protocol_version="2024-11-05",
        client_info={"name": "doc-validator", "version": "1.0"}
    )

    session_id = init_response.session_id

    yield {
        "client": client,
        "session_id": session_id,
        "context": {}  # Shared state between examples
    }

    # Cleanup
    await client.close()

def test_example_with_session(mcp_session, code_block):
    """Test example using persistent session."""
    # Inject session context into code execution
    namespace = {
        "client": mcp_session["client"],
        "session_id": mcp_session["session_id"]
    }

    exec(code_block, namespace)

    # Preserve outputs for next example
    mcp_session["context"].update(namespace)
```

**Benefits**:
- Single initialization for all tests in a file
- State preservation (session IDs, query results)
- Realistic MCP workflow testing
- Faster execution (avoid repeated initialization)

---

### Q5: What metadata format should identify testable code blocks?

**Challenge**: Not all code blocks should be executed (example outputs, pseudocode, incomplete snippets).

**Solution: Comment-based Metadata Convention**

````markdown
```python
# test: true
# requires: mcp_session
# timeout: 10
from mcp.client import Client
...
```
````

**Metadata Keys**:
- `test: true|false` - Whether to execute (default: false for safety)
- `requires: fixture1, fixture2` - Required pytest fixtures
- `timeout: seconds` - Execution timeout
- `expected_output: pattern` - Regex pattern for stdout validation
- `expected_error: ErrorClass` - Expected exception (for error examples)
- `setup: code` - Code to run before block
- `teardown: code` - Code to run after block

**Parser Implementation**:
```python
def parse_code_metadata(code_block: str) -> dict:
    """Extract metadata from code block comments."""
    metadata = {
        "test": False,  # Safe default
        "requires": [],
        "timeout": 30,
        "expected_output": None,
        "expected_error": None
    }

    for line in code_block.split("\n"):
        if line.strip().startswith("#"):
            if "test:" in line:
                metadata["test"] = "true" in line.lower()
            elif "requires:" in line:
                metadata["requires"] = [
                    f.strip()
                    for f in line.split("requires:")[1].split(",")
                ]
            # ... parse other metadata

    return metadata
```

**Rationale**:
- Explicit opt-in prevents accidental execution
- Declarative dependencies (pytest fixtures)
- Visible in documentation (as comments)
- No separate metadata files to maintain

---

## Implementation Architecture

### Component Overview

```
scripts/validate-docs.py          # CLI entry point
tests/docs/
├── conftest.py                   # Pytest fixtures (mcp_session, server)
├── test_code_examples.py         # Main test discovery
├── parsers/
│   ├── markdown_parser.py        # Mistune-based extraction
│   └── metadata_parser.py        # Comment metadata extraction
├── executors/
│   ├── python_executor.py        # Execute Python blocks
│   ├── bash_executor.py          # Execute Bash blocks
│   └── json_validator.py         # Validate JSON/YAML
└── validators/
    ├── output_validator.py       # Compare outputs to expected
    └── mcp_validator.py          # MCP-specific validations
```

### Core Test Discovery Logic

```python
# tests/docs/test_code_examples.py
import pytest
from pathlib import Path
from .parsers.markdown_parser import extract_code_blocks
from .parsers.metadata_parser import parse_metadata
from .executors import get_executor

def collect_doc_tests():
    """Discover all testable code blocks in docs/."""
    docs_dir = Path("docs")
    test_cases = []

    for md_file in docs_dir.rglob("*.md"):
        blocks = extract_code_blocks(md_file)

        for idx, block in enumerate(blocks):
            metadata = parse_metadata(block["code"])

            if metadata["test"]:
                test_cases.append({
                    "file": md_file,
                    "block_id": f"{md_file.stem}_{idx}",
                    "language": block["language"],
                    "code": block["code"],
                    "metadata": metadata
                })

    return test_cases

@pytest.mark.parametrize("test_case", collect_doc_tests())
def test_code_example(test_case, request):
    """Execute a single code block from documentation."""
    # Get executor for language
    executor = get_executor(test_case["language"])

    # Resolve required fixtures
    fixtures = {
        name: request.getfixturevalue(name)
        for name in test_case["metadata"]["requires"]
    }

    # Execute with timeout
    result = executor.execute(
        test_case["code"],
        fixtures=fixtures,
        timeout=test_case["metadata"]["timeout"]
    )

    # Validate result
    if test_case["metadata"]["expected_output"]:
        assert re.match(
            test_case["metadata"]["expected_output"],
            result.stdout
        )

    if test_case["metadata"]["expected_error"]:
        assert isinstance(result.exception, test_case["metadata"]["expected_error"])
    else:
        assert result.success, f"Execution failed: {result.stderr}"
```

### Markdown Parser (using mistune)

```python
# tests/docs/parsers/markdown_parser.py
import mistune
from typing import List, Dict

class CodeBlockExtractor(mistune.HTMLRenderer):
    """Custom renderer to extract code blocks."""

    def __init__(self):
        super().__init__()
        self.code_blocks = []

    def block_code(self, code: str, info: str = None):
        """Capture code blocks during parsing."""
        language = info.split()[0] if info else "text"

        self.code_blocks.append({
            "language": language,
            "code": code,
            "info": info
        })

        return ""  # Don't render, just collect

def extract_code_blocks(markdown_file: Path) -> List[Dict]:
    """Extract all code blocks from a Markdown file."""
    content = markdown_file.read_text()

    renderer = CodeBlockExtractor()
    markdown = mistune.Markdown(renderer=renderer)
    markdown(content)

    return renderer.code_blocks
```

---

## Alternatives Considered

### Alternative 1: Manual Testing with Checklist

**Approach**: Maintain a checklist of examples to test manually before releases.

**Pros**:
- No development effort
- Flexible testing (human judgment)

**Cons**:
- Time-consuming (hours per release)
- Error-prone (missed examples)
- Doesn't scale (documentation grows)
- Violates SC-007 (95% automated success rate)

**Verdict**: ❌ Rejected - fails success criteria, unsustainable

---

### Alternative 2: GitHub Actions with codedown + shell scripts

**Approach**: Use codedown to extract code blocks, then shell scripts to execute them.

```bash
# .github/workflows/validate-docs.sh
codedown python < docs/getting-started/setup.md > /tmp/setup.py
python /tmp/setup.py || exit 1

codedown bash < docs/api-reference/curl-examples.md > /tmp/curl-tests.sh
bash /tmp/curl-tests.sh || exit 1
```

**Pros**:
- Simple tooling
- Fast execution
- Language-agnostic

**Cons**:
- No metadata support (all or nothing)
- No session state preservation
- No output validation (only exit codes)
- Brittle (hard to debug failures)
- No pytest integration

**Verdict**: ⚠️ Viable but limited - lacks MCP session management

---

### Alternative 3: pytest-examples (https://github.com/samuelcolvin/pytest-examples)

**Approach**: Samuel Colvin's tool for testing code in Markdown/RST docs.

**Pros**:
- Maintained by Pydantic author
- Good Python support
- Pytest integration

**Cons**:
- Python-only (no Bash/curl)
- Requires special comment syntax
- No custom validation logic
- Doesn't handle stateful workflows (MCP sessions)

**Verdict**: ⚠️ Viable for Python examples only - 60% coverage

---

## Success Metrics & Validation

### SC-007: 95% Success Rate

**Measurement**:
```python
# tests/docs/test_code_examples.py
def test_documentation_success_rate(pytestconfig):
    """Ensure 95%+ of code examples pass validation."""
    result = pytestconfig.cache.get("docs/validation_rate", None)

    if result:
        success_rate = result["passed"] / result["total"]
        assert success_rate >= 0.95, (
            f"Documentation success rate {success_rate:.1%} "
            f"below 95% threshold"
        )
```

**Tracking**:
- Store test results in `.pytest_cache`
- Generate weekly reports
- Alert on regression below 95%

### SC-005: Documentation Lag < 2 Weeks

**Measurement**:
- Git blame on `docs/**/*.md` vs `server.py`
- Compare last modified timestamps
- Alert if doc change lags code change by >14 days

**Automation**:
```python
# scripts/check-doc-freshness.py
def check_freshness():
    server_modified = Path("server.py").stat().st_mtime

    for doc in Path("docs").rglob("*.md"):
        doc_modified = doc.stat().st_mtime
        lag_days = (server_modified - doc_modified) / 86400

        if lag_days > 14:
            print(f"⚠️ {doc} is {lag_days:.0f} days behind code")
```

---

## Recommended Implementation Plan

### Phase 1: Core Infrastructure (Days 1-2)
1. Set up `tests/docs/` structure
2. Implement Markdown parser with mistune
3. Create metadata parser
4. Build Python executor with pytest integration

### Phase 2: Executors & Validators (Days 3-4)
1. Implement Bash executor (subprocess)
2. Implement JSON/YAML validator
3. Create MCP session fixture
4. Build output validators (regex, exact match)

### Phase 3: CI/CD Integration (Day 5)
1. Create GitHub Actions workflow
2. Add pytest configuration
3. Set up reporting (JSON artifacts)
4. Document contribution guidelines

### Phase 4: Documentation Migration (Ongoing)
1. Add `# test: true` to existing examples
2. Validate each example runs successfully
3. Fix broken examples (update to current API)
4. Achieve 95% success rate

---

## Dependencies

**New Requirements**:
```txt
# Documentation validation (dev only)
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-timeout>=2.1.0
mistune>=3.0.0
```

**Justification**:
- `pytest`: Testing framework (project standard)
- `pytest-asyncio`: Async MCP client support
- `pytest-timeout`: Prevent hanging tests
- `mistune`: Fast, compliant Markdown parser

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Examples become outdated | High | Medium | Automated CI/CD validation catches breakage |
| MCP API changes break examples | Medium | High | Version pin in docs, migration guide |
| Validation too slow (>5min) | Low | Medium | Parallel execution, fixture caching |
| False negatives (flaky tests) | Medium | Medium | Retry logic, timeout tuning |
| Developers skip validation | Low | High | Make validation part of PR checks |

---

## Conclusion

**Selected Approach**: Custom pytest plugin with Markdown parsing

**Rationale**:
1. **Comprehensive Coverage**: Supports Python, Bash, JSON, YAML (all doc languages)
2. **MCP-Aware**: Session management, stateful workflows
3. **Pytest Integration**: Leverages existing infrastructure
4. **Flexible Validation**: Output patterns, error expectations, custom logic
5. **CI/CD Ready**: GitHub Actions integration
6. **Maintainable**: Standard pytest patterns, clear structure
7. **Meets Success Criteria**: Achieves 95% success rate (SC-007)

**Tradeoffs**:
- Initial development effort (3-5 days)
- Custom code to maintain

**Alternatives Rejected**:
- Manual testing: Doesn't scale, violates SC-007
- Shell scripts: Lacks session management, limited validation
- pytest-examples: Python-only, no MCP workflows

**Next Steps**:
1. Create `tests/docs/` structure
2. Implement Markdown parser
3. Build Python executor
4. Add first validated examples
5. Expand to Bash/JSON validators
6. Integrate with CI/CD

---

## References

- [pytest documentation](https://docs.pytest.org/)
- [mistune documentation](https://mistune.lepture.com/)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
- [pytest-markdown-docs](https://github.com/modal-labs/pytest-markdown-docs)
- [pytest-examples](https://github.com/samuelcolvin/pytest-examples)
- [codedown](https://github.com/earldouglas/codedown)

---

**Research Status**: ✅ Complete
**Reviewed By**: Pending
**Approved For Implementation**: Pending
