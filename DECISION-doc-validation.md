# Decision: Code Validation in Documentation

**Date**: 2026-01-06
**Context**: Feature 001 - Comprehensive System Documentation
**Requirement**: Achieve 95% automated validation of code examples in Markdown documentation

---

## Decision: Custom pytest Plugin with Markdown Parser

### Rationale

We will build a custom pytest plugin that:
1. Parses Markdown files using `mistune` to extract fenced code blocks
2. Executes Python, Bash, and validates JSON/YAML examples
3. Manages MCP session state across multi-step examples
4. Integrates with GitHub Actions for CI/CD validation

**Why this approach fits our needs**:

- **Multi-language Support**: Our documentation includes Python (MCP client code), Bash (curl commands), JSON (config files), and YAML. Existing tools like `pytest-markdown-docs` only handle Python.

- **MCP Protocol Awareness**: The Model Context Protocol requires session initialization before tool calls. Our validator needs to preserve session state across code blocks in the same document (e.g., initialize → list_communes → query). Existing doctest tools execute blocks in isolation.

- **GraphRAG-Specific Validation**: We need to test against a live MCP server (`http://localhost:8080/mcp`), not just validate syntax. Custom validation logic can check response formats, entity counts, provenance chains, etc.

- **Opt-in Safety**: Using comment metadata (`# test: true`) prevents accidental execution of incomplete examples or pseudocode. This is safer than tools that auto-execute everything.

- **Pytest Ecosystem**: Leverages existing pytest infrastructure (fixtures, parametrization, reporting). Team already familiar with pytest patterns.

- **95% Success Rate**: Automated CI/CD testing ensures code examples stay in sync with codebase changes, meeting SC-007 requirement.

---

### Implementation Outline

#### 1. Project Structure

```
tests/docs/
├── conftest.py                   # Pytest fixtures (mcp_session, server)
├── test_code_examples.py         # Main test discovery and execution
├── parsers/
│   ├── markdown_parser.py        # Extract code blocks with mistune
│   └── metadata_parser.py        # Parse comment metadata (# test: true)
├── executors/
│   ├── python_executor.py        # Execute Python blocks
│   ├── bash_executor.py          # Execute Bash/curl blocks
│   └── json_validator.py         # Validate JSON/YAML syntax
└── validators/
    ├── output_validator.py       # Compare outputs to expected patterns
    └── mcp_validator.py          # MCP-specific response validation

scripts/
└── validate-docs.py              # CLI wrapper for pytest
```

#### 2. Metadata Convention

Mark testable code blocks with comments:

````markdown
```python
# test: true
# requires: mcp_session
# timeout: 10
# expected_output: \d+ communes found

from mcp.client import Client
response = await client.call_tool("grand_debat_list_communes", {})
print(f"{len(response['communes'])} communes found")
```
````

**Metadata keys**:
- `test: true` - Execute this block (default: false for safety)
- `requires: fixture1, fixture2` - Required pytest fixtures
- `timeout: seconds` - Execution timeout
- `expected_output: regex` - Validate stdout against pattern

#### 3. MCP Session Fixture

```python
# tests/docs/conftest.py
import pytest
from mcp.client import Client

@pytest.fixture(scope="module")
async def mcp_session():
    """Persistent MCP session for documentation tests."""
    client = Client("http://localhost:8080/mcp")

    # Initialize session once per test module
    init_response = await client.initialize(
        protocol_version="2024-11-05",
        client_info={"name": "doc-validator", "version": "1.0"}
    )

    yield {
        "client": client,
        "session_id": init_response.session_id,
        "context": {}  # Shared state between examples
    }

    await client.close()
```

#### 4. Test Discovery

```python
# tests/docs/test_code_examples.py
import pytest
from pathlib import Path
from .parsers.markdown_parser import extract_code_blocks
from .parsers.metadata_parser import parse_metadata

def collect_doc_tests():
    """Discover all testable code blocks in docs/."""
    test_cases = []

    for md_file in Path("docs").rglob("*.md"):
        blocks = extract_code_blocks(md_file)

        for idx, block in enumerate(blocks):
            metadata = parse_metadata(block["code"])

            if metadata["test"]:  # Only collect marked blocks
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
    executor = get_executor(test_case["language"])

    # Resolve fixtures (e.g., mcp_session)
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

    # Validate output
    assert result.success, f"Failed: {result.stderr}"
```

#### 5. Markdown Parser

```python
# tests/docs/parsers/markdown_parser.py
import mistune

class CodeBlockExtractor(mistune.HTMLRenderer):
    """Extract code blocks during Markdown parsing."""

    def __init__(self):
        super().__init__()
        self.code_blocks = []

    def block_code(self, code: str, info: str = None):
        language = info.split()[0] if info else "text"

        self.code_blocks.append({
            "language": language,
            "code": code
        })

        return ""  # Don't render, just collect

def extract_code_blocks(markdown_file: Path):
    """Extract all code blocks from a Markdown file."""
    content = markdown_file.read_text()

    renderer = CodeBlockExtractor()
    markdown = mistune.Markdown(renderer=renderer)
    markdown(content)

    return renderer.code_blocks
```

#### 6. Python Executor

```python
# tests/docs/executors/python_executor.py
import sys
from io import StringIO

def execute_python(code: str, fixtures: dict, timeout: int):
    """Execute Python code block with fixtures."""
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        # Create namespace with fixtures
        namespace = fixtures.copy()

        # Execute code
        exec(code, namespace)

        return {
            "success": True,
            "stdout": captured_output.getvalue(),
            "stderr": "",
            "exception": None
        }

    except Exception as e:
        return {
            "success": False,
            "stdout": captured_output.getvalue(),
            "stderr": str(e),
            "exception": e
        }

    finally:
        sys.stdout = old_stdout
```

#### 7. Bash Executor

```python
# tests/docs/executors/bash_executor.py
import subprocess

def execute_bash(code: str, fixtures: dict, timeout: int):
    """Execute Bash code block."""
    # Inject environment variables from fixtures
    env = os.environ.copy()
    if "mcp_session" in fixtures:
        env["MCP_SESSION_ID"] = fixtures["mcp_session"]["session_id"]

    result = subprocess.run(
        code,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env
    )

    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exception": None
    }
```

#### 8. CI/CD Integration

```yaml
# .github/workflows/validate-docs.yml
name: Validate Documentation

on:
  push:
    paths:
      - 'docs/**/*.md'
      - 'server.py'
  pull_request:

jobs:
  validate-docs:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-timeout mistune

      - name: Start MCP server
        run: |
          python server.py --port 8080 &
          sleep 5  # Wait for server startup
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      - name: Run documentation validation
        run: pytest tests/docs/ -v --tb=short

      - name: Check success rate
        run: |
          # Fail if <95% examples pass
          python scripts/check-success-rate.py
```

#### 9. Developer Workflow

**Adding a new code example**:

1. Write example in Markdown:
   ````markdown
   ```python
   # test: true
   # requires: mcp_session

   response = await mcp_session["client"].call_tool(
       "grand_debat_query",
       {"commune_id": "Rochefort", "query": "fiscalité"}
   )
   print(response["answer"])
   ```
   ````

2. Validate locally:
   ```bash
   pytest tests/docs/test_code_examples.py::test_code_example[api-reference/mcp-tools_3] -v
   ```

3. Commit and push - CI validates automatically

---

### Alternatives Considered

#### Alternative 1: pytest-markdown-docs

**Why not chosen**:
- Python-only, no Bash/curl support
- Our docs include critical Bash examples (MCP initialization with curl)
- Doesn't handle MCP session state preservation
- Less control over validation logic

**When to reconsider**: If we decide to separate Python and Bash examples into different validation workflows

---

#### Alternative 2: Manual Testing Checklist

**Why not chosen**:
- Time-consuming (hours per release)
- Error-prone (easy to miss examples)
- Doesn't scale as documentation grows
- Violates SC-007 requirement (95% automated validation)

**When to reconsider**: Never - automation is essential for maintainability

---

#### Alternative 3: codedown + Shell Scripts

**Why not chosen**:
- No metadata support (can't mark blocks as testable)
- No session state preservation
- Only validates exit codes, not outputs
- Harder to debug failures
- No pytest integration

**When to reconsider**: If we need to validate documentation in non-Python projects

---

#### Alternative 4: pytest-examples (Samuel Colvin)

**Why not chosen**:
- Python-only (no Bash/curl)
- Requires special comment syntax incompatible with our needs
- Doesn't handle stateful workflows (MCP sessions)
- 60% coverage vs our 95% requirement

**When to reconsider**: If MCP protocol becomes Python-native (no curl/HTTP needed)

---

### Success Metrics

**SC-007**: 95% of code examples execute successfully
- Tracked via pytest exit codes
- Weekly reports from CI/CD runs
- Alert on regression below 95%

**SC-005**: Documentation lag < 2 weeks
- Monitor git timestamps (docs vs code)
- Alert if doc changes lag code changes >14 days

**Developer Experience**:
- Local validation in <2 minutes
- Clear error messages for failures
- Easy to add new examples (just add `# test: true`)

---

### Dependencies

```txt
# Add to requirements.txt (dev section)
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-timeout>=2.1.0
mistune>=3.0.0
```

**Why these libraries**:
- `pytest`: Standard testing framework, team already uses it
- `pytest-asyncio`: Required for async MCP client
- `pytest-timeout`: Prevent hanging tests (MCP network calls)
- `mistune`: Fast, spec-compliant Markdown parser

---

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Examples become outdated | CI runs on every doc/code change |
| MCP API changes break examples | Version pin documented, migration guide |
| Validation too slow (>5min) | Parallel pytest execution, fixture caching |
| Flaky tests (network issues) | Retry logic, timeout tuning, local server |
| Developers skip validation | Make it a required PR check |

---

### Timeline

- **Phase 1** (Days 1-2): Core infrastructure (parser, metadata, Python executor)
- **Phase 2** (Days 3-4): Bash/JSON executors, MCP fixtures, validators
- **Phase 3** (Day 5): CI/CD integration, reporting
- **Phase 4** (Ongoing): Migrate existing examples, achieve 95% success rate

---

### Conclusion

Custom pytest plugin provides the flexibility, MCP awareness, and multi-language support needed to validate our documentation against a live GraphRAG MCP server. The 3-5 day implementation effort is justified by long-term maintainability, automated validation, and meeting the 95% success rate requirement (SC-007).

The metadata-based opt-in approach (`# test: true`) ensures safety while providing clear documentation conventions. Integration with pytest leverages existing team knowledge and infrastructure.

**Approved**: Pending
**Implementation Owner**: TBD
**Target Completion**: TBD
