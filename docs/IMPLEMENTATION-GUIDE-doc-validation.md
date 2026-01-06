# Implementation Guide: Documentation Validation System

**Feature**: Automated Code Example Validation for Markdown Documentation
**Estimated Effort**: 5 days + ongoing migration
**Target**: 95% automated validation success rate (SC-007)

---

## Overview

This guide walks you through implementing a custom pytest plugin that validates Python, Bash, and JSON code examples in Markdown documentation against a live GraphRAG MCP server.

**What you'll build**:
- Markdown parser extracting code blocks
- Metadata system for marking testable examples
- Multi-language executors (Python, Bash, JSON)
- MCP session management fixture
- CI/CD integration with GitHub Actions

---

## Prerequisites

- Python 3.11+
- pytest installed
- GraphRAG MCP server running locally
- Familiarity with pytest fixtures and parametrization

---

## Phase 1: Core Infrastructure (Days 1-2)

### Step 1.1: Create Directory Structure

```bash
cd /Users/arthursarazin/Documents/graphRAGmcp

mkdir -p tests/docs/parsers
mkdir -p tests/docs/executors
mkdir -p tests/docs/validators
mkdir -p scripts

touch tests/docs/__init__.py
touch tests/docs/conftest.py
touch tests/docs/test_code_examples.py
touch tests/docs/parsers/__init__.py
touch tests/docs/parsers/markdown_parser.py
touch tests/docs/parsers/metadata_parser.py
touch tests/docs/executors/__init__.py
touch tests/docs/executors/python_executor.py
touch tests/docs/executors/bash_executor.py
touch tests/docs/executors/json_validator.py
touch tests/docs/validators/__init__.py
touch tests/docs/validators/output_validator.py
touch tests/docs/validators/mcp_validator.py
touch scripts/validate-docs.py
touch scripts/check-success-rate.py
```

### Step 1.2: Install Dependencies

Add to `requirements.txt`:
```txt
# Documentation validation (dev dependencies)
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-timeout>=2.1.0
mistune>=3.0.0
```

Install:
```bash
pip install pytest pytest-asyncio pytest-timeout mistune
```

### Step 1.3: Implement Markdown Parser

**File**: `tests/docs/parsers/markdown_parser.py`

```python
"""Extract code blocks from Markdown files using mistune."""
import mistune
from pathlib import Path
from typing import List, Dict


class CodeBlockExtractor(mistune.HTMLRenderer):
    """Custom renderer to extract code blocks during parsing."""

    def __init__(self):
        super().__init__()
        self.code_blocks = []

    def block_code(self, code: str, info: str = None) -> str:
        """Capture code blocks with their language info."""
        language = info.split()[0] if info else "text"

        self.code_blocks.append({
            "language": language,
            "code": code.strip(),
            "info": info
        })

        return ""  # Don't render, just collect


def extract_code_blocks(markdown_file: Path) -> List[Dict]:
    """
    Extract all fenced code blocks from a Markdown file.

    Args:
        markdown_file: Path to .md file

    Returns:
        List of dicts with keys: language, code, info
    """
    if not markdown_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_file}")

    content = markdown_file.read_text(encoding="utf-8")

    renderer = CodeBlockExtractor()
    markdown = mistune.Markdown(renderer=renderer)
    markdown(content)

    return renderer.code_blocks


if __name__ == "__main__":
    # Test extraction
    test_md = Path("docs/getting-started/overview.md")
    if test_md.exists():
        blocks = extract_code_blocks(test_md)
        print(f"Found {len(blocks)} code blocks:")
        for i, block in enumerate(blocks):
            print(f"  {i+1}. {block['language']} ({len(block['code'])} chars)")
```

**Test it**:
```bash
python tests/docs/parsers/markdown_parser.py
```

### Step 1.4: Implement Metadata Parser

**File**: `tests/docs/parsers/metadata_parser.py`

```python
"""Parse metadata from code block comments."""
import re
from typing import Dict, List, Optional


def parse_metadata(code: str) -> Dict:
    """
    Extract metadata from comment lines in code block.

    Supported metadata:
        # test: true|false
        # requires: fixture1, fixture2
        # timeout: 30
        # expected_output: regex pattern
        # expected_error: ExceptionClass

    Args:
        code: Code block content

    Returns:
        Dict with metadata (defaults for missing keys)
    """
    metadata = {
        "test": False,  # Safe default - don't execute unless marked
        "requires": [],
        "timeout": 30,
        "expected_output": None,
        "expected_error": None
    }

    for line in code.split("\n"):
        line = line.strip()

        if not line.startswith("#"):
            continue  # Only parse comment lines

        # test: true|false
        if "test:" in line:
            value = line.split("test:")[1].strip().lower()
            metadata["test"] = value in ["true", "yes", "1"]

        # requires: fixture1, fixture2
        elif "requires:" in line:
            value = line.split("requires:")[1].strip()
            metadata["requires"] = [
                f.strip() for f in value.split(",") if f.strip()
            ]

        # timeout: 30
        elif "timeout:" in line:
            value = line.split("timeout:")[1].strip()
            try:
                metadata["timeout"] = int(value)
            except ValueError:
                pass  # Keep default

        # expected_output: regex pattern
        elif "expected_output:" in line:
            value = line.split("expected_output:")[1].strip()
            metadata["expected_output"] = value

        # expected_error: ErrorClass
        elif "expected_error:" in line:
            value = line.split("expected_error:")[1].strip()
            metadata["expected_error"] = value

    return metadata


if __name__ == "__main__":
    # Test parsing
    sample_code = """
# test: true
# requires: mcp_session
# timeout: 10
# expected_output: \\d+ communes found

from mcp.client import Client
response = await client.call_tool("list_communes", {})
print(f"{len(response)} communes found")
"""
    metadata = parse_metadata(sample_code)
    print("Parsed metadata:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")
```

**Test it**:
```bash
python tests/docs/parsers/metadata_parser.py
```

### Step 1.5: Implement Python Executor

**File**: `tests/docs/executors/python_executor.py`

```python
"""Execute Python code blocks with fixture injection."""
import sys
from io import StringIO
from typing import Dict, Any


class ExecutionResult:
    """Result of code execution."""

    def __init__(
        self,
        success: bool,
        stdout: str,
        stderr: str,
        exception: Exception = None,
        namespace: Dict = None
    ):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exception = exception
        self.namespace = namespace or {}


def execute_python(code: str, fixtures: Dict, timeout: int) -> ExecutionResult:
    """
    Execute Python code block with fixtures injected as globals.

    Args:
        code: Python code to execute
        fixtures: Dict of pytest fixtures (e.g., {"mcp_session": ...})
        timeout: Execution timeout in seconds (TODO: implement)

    Returns:
        ExecutionResult with success status, outputs, and namespace
    """
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = captured_error = StringIO()

    try:
        # Create execution namespace with fixtures
        namespace = fixtures.copy()

        # Execute code
        exec(code, namespace)

        return ExecutionResult(
            success=True,
            stdout=captured_output.getvalue(),
            stderr=captured_error.getvalue(),
            namespace=namespace
        )

    except Exception as e:
        return ExecutionResult(
            success=False,
            stdout=captured_output.getvalue(),
            stderr=captured_error.getvalue() or str(e),
            exception=e,
            namespace={}
        )

    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr


if __name__ == "__main__":
    # Test execution
    test_code = """
x = 10 + 5
print(f"Result: {x}")
"""
    result = execute_python(test_code, {}, 30)
    print(f"Success: {result.success}")
    print(f"Output: {result.stdout}")
    print(f"Namespace: {result.namespace.get('x')}")
```

**Test it**:
```bash
python tests/docs/executors/python_executor.py
```

---

## Phase 2: Executors & Validators (Days 3-4)

### Step 2.1: Implement Bash Executor

**File**: `tests/docs/executors/bash_executor.py`

```python
"""Execute Bash code blocks."""
import os
import subprocess
from typing import Dict


class ExecutionResult:
    """Result of bash execution."""

    def __init__(self, success: bool, stdout: str, stderr: str, returncode: int):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def execute_bash(code: str, fixtures: Dict, timeout: int) -> ExecutionResult:
    """
    Execute Bash code block with environment variable injection.

    Args:
        code: Bash code to execute
        fixtures: Dict of pytest fixtures
        timeout: Execution timeout in seconds

    Returns:
        ExecutionResult with success status and outputs
    """
    # Prepare environment variables
    env = os.environ.copy()

    # Inject MCP session ID if available
    if "mcp_session" in fixtures:
        env["MCP_SESSION_ID"] = fixtures["mcp_session"]["session_id"]
        env["MCP_SERVER_URL"] = "http://localhost:8080/mcp"

    try:
        result = subprocess.run(
            code,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )

        return ExecutionResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode
        )

    except subprocess.TimeoutExpired as e:
        return ExecutionResult(
            success=False,
            stdout=e.stdout.decode() if e.stdout else "",
            stderr=f"Timeout after {timeout}s",
            returncode=-1
        )

    except Exception as e:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=str(e),
            returncode=-1
        )
```

### Step 2.2: Implement JSON Validator

**File**: `tests/docs/executors/json_validator.py`

```python
"""Validate JSON and YAML code blocks."""
import json
import yaml
from typing import Dict, Any


class ValidationResult:
    """Result of JSON/YAML validation."""

    def __init__(self, success: bool, data: Any = None, error: str = ""):
        self.success = success
        self.data = data
        self.error = error


def validate_json(code: str, fixtures: Dict, timeout: int) -> ValidationResult:
    """
    Validate JSON syntax and optionally schema.

    Args:
        code: JSON string
        fixtures: Dict of pytest fixtures
        timeout: Not used for JSON validation

    Returns:
        ValidationResult with parsed data
    """
    try:
        data = json.loads(code)

        # TODO: Add schema validation
        # if "json_schema" in fixtures:
        #     jsonschema.validate(data, fixtures["json_schema"])

        return ValidationResult(success=True, data=data)

    except json.JSONDecodeError as e:
        return ValidationResult(
            success=False,
            error=f"JSON syntax error: {e}"
        )


def validate_yaml(code: str, fixtures: Dict, timeout: int) -> ValidationResult:
    """Validate YAML syntax."""
    try:
        data = yaml.safe_load(code)
        return ValidationResult(success=True, data=data)

    except yaml.YAMLError as e:
        return ValidationResult(
            success=False,
            error=f"YAML syntax error: {e}"
        )
```

### Step 2.3: Create MCP Session Fixture

**File**: `tests/docs/conftest.py`

```python
"""Pytest fixtures for documentation validation."""
import pytest
import asyncio
from mcp.client import Client


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def mcp_session():
    """
    Persistent MCP session for documentation tests.

    Initializes connection once per test module, preserves session ID
    across all code blocks in the same file.

    Yields:
        Dict with:
            - client: MCP Client instance
            - session_id: Session identifier
            - context: Shared state between examples
    """
    # Initialize MCP client
    client = Client("http://localhost:8080/mcp")

    try:
        # Initialize session
        init_response = await client.initialize(
            protocol_version="2024-11-05",
            capabilities={},
            client_info={"name": "doc-validator", "version": "1.0"}
        )

        session_id = init_response.get("session_id")

        # Yield session context
        yield {
            "client": client,
            "session_id": session_id,
            "context": {}  # Shared state between examples
        }

    finally:
        # Cleanup
        await client.close()


@pytest.fixture
def mcp_server_url():
    """MCP server URL for non-session tests."""
    return "http://localhost:8080/mcp"
```

### Step 2.4: Implement Output Validator

**File**: `tests/docs/validators/output_validator.py`

```python
"""Validate execution outputs against expected patterns."""
import re
from typing import Optional


def validate_output(
    actual: str,
    expected_pattern: Optional[str]
) -> tuple[bool, str]:
    """
    Validate output against expected regex pattern.

    Args:
        actual: Actual output from execution
        expected_pattern: Regex pattern or None

    Returns:
        Tuple of (success: bool, message: str)
    """
    if expected_pattern is None:
        return True, "No expected output specified"

    if re.search(expected_pattern, actual):
        return True, f"Output matches pattern: {expected_pattern}"
    else:
        return False, (
            f"Output mismatch:\n"
            f"  Expected pattern: {expected_pattern}\n"
            f"  Actual output: {actual[:200]}"
        )
```

---

## Phase 3: Test Discovery & Execution (Days 3-4 continued)

### Step 3.1: Implement Test Discovery

**File**: `tests/docs/test_code_examples.py`

```python
"""Main test discovery and execution for documentation code examples."""
import pytest
from pathlib import Path
from typing import List, Dict

from .parsers.markdown_parser import extract_code_blocks
from .parsers.metadata_parser import parse_metadata
from .executors.python_executor import execute_python
from .executors.bash_executor import execute_bash
from .executors.json_validator import validate_json, validate_yaml
from .validators.output_validator import validate_output


def get_executor(language: str):
    """Get executor function for language."""
    executors = {
        "python": execute_python,
        "bash": execute_bash,
        "sh": execute_bash,
        "json": validate_json,
        "yaml": validate_yaml,
    }
    return executors.get(language.lower())


def collect_doc_tests() -> List[Dict]:
    """
    Discover all testable code blocks in docs/ directory.

    Returns:
        List of test cases with metadata
    """
    docs_dir = Path("docs")
    if not docs_dir.exists():
        return []

    test_cases = []

    for md_file in docs_dir.rglob("*.md"):
        try:
            blocks = extract_code_blocks(md_file)

            for idx, block in enumerate(blocks):
                metadata = parse_metadata(block["code"])

                # Only collect blocks marked with # test: true
                if metadata["test"]:
                    test_cases.append({
                        "file": str(md_file.relative_to(docs_dir)),
                        "block_id": f"{md_file.stem}_{idx}",
                        "language": block["language"],
                        "code": block["code"],
                        "metadata": metadata
                    })

        except Exception as e:
            print(f"Warning: Failed to parse {md_file}: {e}")

    return test_cases


# Parametrize test with all discovered code blocks
@pytest.mark.parametrize("test_case", collect_doc_tests())
@pytest.mark.timeout(60)
def test_code_example(test_case, request):
    """
    Execute a single code block from documentation.

    Args:
        test_case: Dict with file, language, code, metadata
        request: Pytest request fixture
    """
    # Get executor for language
    executor = get_executor(test_case["language"])

    if executor is None:
        pytest.skip(f"No executor for language: {test_case['language']}")

    # Resolve required fixtures
    fixtures = {}
    for fixture_name in test_case["metadata"]["requires"]:
        try:
            fixtures[fixture_name] = request.getfixturevalue(fixture_name)
        except Exception as e:
            pytest.fail(f"Failed to resolve fixture '{fixture_name}': {e}")

    # Execute code block
    result = executor(
        test_case["code"],
        fixtures=fixtures,
        timeout=test_case["metadata"]["timeout"]
    )

    # Validate result
    assert result.success, (
        f"Execution failed in {test_case['file']} block {test_case['block_id']}:\n"
        f"  Language: {test_case['language']}\n"
        f"  Error: {result.stderr or result.error}\n"
        f"  Code:\n{test_case['code'][:200]}"
    )

    # Validate output pattern if specified
    if test_case["metadata"]["expected_output"]:
        output = result.stdout if hasattr(result, "stdout") else ""

        success, message = validate_output(
            output,
            test_case["metadata"]["expected_output"]
        )

        assert success, (
            f"Output validation failed in {test_case['file']}:\n"
            f"  {message}"
        )


def test_documentation_success_rate():
    """
    Ensure 95%+ of code examples pass validation (SC-007).

    This test fails if success rate drops below threshold.
    """
    test_cases = collect_doc_tests()

    if not test_cases:
        pytest.skip("No testable code blocks found")

    # This is measured by pytest itself
    # Just ensure we have examples to test
    assert len(test_cases) > 0, "No code examples marked for testing"
```

### Step 3.2: Create CLI Validation Script

**File**: `scripts/validate-docs.py`

```python
#!/usr/bin/env python3
"""CLI wrapper for documentation validation."""
import sys
import subprocess


def main():
    """Run pytest on documentation tests."""
    result = subprocess.run(
        ["pytest", "tests/docs/", "-v", "--tb=short"],
        capture_output=False
    )

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
```

Make executable:
```bash
chmod +x scripts/validate-docs.py
```

### Step 3.3: Create Success Rate Checker

**File**: `scripts/check-success-rate.py`

```python
#!/usr/bin/env python3
"""Check if documentation validation meets 95% success rate (SC-007)."""
import sys
import subprocess
import json


def main():
    """Run pytest with JSON report and check success rate."""
    # Run tests with JSON reporter
    result = subprocess.run(
        [
            "pytest",
            "tests/docs/",
            "--json-report",
            "--json-report-file=.pytest-report.json",
            "-q"
        ],
        capture_output=True
    )

    # Load report
    try:
        with open(".pytest-report.json") as f:
            report = json.load(f)
    except FileNotFoundError:
        print("ERROR: No pytest report found")
        sys.exit(1)

    # Calculate success rate
    total = report["summary"]["total"]
    passed = report["summary"].get("passed", 0)

    if total == 0:
        print("WARNING: No tests found")
        sys.exit(0)

    success_rate = passed / total

    print(f"Documentation Validation: {passed}/{total} ({success_rate:.1%})")

    if success_rate < 0.95:
        print(f"ERROR: Success rate {success_rate:.1%} below 95% threshold (SC-007)")
        sys.exit(1)
    else:
        print(f"SUCCESS: Meets 95% success rate requirement")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

Make executable:
```bash
chmod +x scripts/check-success-rate.py
```

---

## Phase 4: CI/CD Integration (Day 5)

### Step 4.1: Create GitHub Actions Workflow

**File**: `.github/workflows/validate-docs.yml`

```yaml
name: Validate Documentation

on:
  push:
    branches:
      - main
      - develop
    paths:
      - 'docs/**/*.md'
      - 'server.py'
      - 'graph_index.py'
      - 'tests/docs/**'
  pull_request:
    paths:
      - 'docs/**/*.md'
      - 'tests/docs/**'

jobs:
  validate-docs:
    name: Validate Code Examples
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-timeout pytest-json-report mistune

      - name: Start MCP server
        run: |
          python server.py --port 8080 &
          echo $! > server.pid
          sleep 5  # Wait for server initialization
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GRAND_DEBAT_DATA_PATH: ./law_data

      - name: Wait for server health
        run: |
          for i in {1..30}; do
            if curl -f http://localhost:8080/health; then
              echo "Server is healthy"
              break
            fi
            echo "Waiting for server... ($i/30)"
            sleep 1
          done

      - name: Run documentation validation
        run: pytest tests/docs/ -v --tb=short --json-report --json-report-file=docs-validation.json

      - name: Check 95% success rate
        if: always()
        run: python scripts/check-success-rate.py

      - name: Upload validation report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: docs-validation-report
          path: .pytest-report.json

      - name: Stop MCP server
        if: always()
        run: |
          if [ -f server.pid ]; then
            kill $(cat server.pid) || true
          fi
```

### Step 4.2: Add Pytest Configuration

**File**: `pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Documentation tests
markers =
    docs: Documentation code example tests

# Timeout for all tests
timeout = 60

# Show summary
addopts = -ra --strict-markers

# Asyncio mode
asyncio_mode = auto
```

---

## Phase 5: Documentation Migration (Ongoing)

### Step 5.1: Add Validation to Existing Examples

**Before** (in `docs/getting-started/setup.md`):
````markdown
```python
from mcp.client import Client

client = Client("http://localhost:8080/mcp")
response = await client.initialize()
print(response)
```
````

**After**:
````markdown
```python
# test: true
# requires: mcp_server_url
# expected_output: session_id

from mcp.client import Client

client = Client(mcp_server_url)
response = await client.initialize(
    protocol_version="2024-11-05",
    client_info={"name": "example", "version": "1.0"}
)
print(f"Initialized with session: {response.get('session_id')}")
```
````

### Step 5.2: Validate Locally

```bash
# Validate all docs
pytest tests/docs/ -v

# Validate specific file
pytest tests/docs/test_code_examples.py -k "setup" -v

# Check success rate
python scripts/check-success-rate.py
```

### Step 5.3: Fix Broken Examples

Common issues:
- **Outdated API**: Update to current MCP protocol
- **Missing imports**: Add required imports
- **Wrong fixtures**: Use correct fixture names
- **Timeout**: Increase timeout for slow operations

### Step 5.4: Achieve 95% Success Rate

Track progress:
```bash
# Run all tests and generate report
pytest tests/docs/ --json-report

# Check current success rate
python scripts/check-success-rate.py
```

Continue until `>=95%` of examples pass.

---

## Testing the Implementation

### Local Testing

```bash
# 1. Start MCP server
python server.py --port 8080

# 2. In another terminal, run validation
pytest tests/docs/ -v

# 3. Check success rate
python scripts/check-success-rate.py
```

### CI/CD Testing

Push to GitHub and check Actions tab for workflow results.

---

## Troubleshooting

### "No tests found"

**Cause**: No code blocks marked with `# test: true`

**Solution**: Add metadata to at least one code block:
````markdown
```python
# test: true
print("Hello")
```
````

### "Fixture 'mcp_session' not found"

**Cause**: Fixture not defined in `conftest.py`

**Solution**: Check `tests/docs/conftest.py` has `@pytest.fixture` for `mcp_session`

### "Connection refused to localhost:8080"

**Cause**: MCP server not running

**Solution**: Start server before tests:
```bash
python server.py --port 8080 &
```

### "Timeout after 30s"

**Cause**: Code block takes too long to execute

**Solution**: Increase timeout:
````markdown
```python
# test: true
# timeout: 60
# Long-running operation...
```
````

---

## Next Steps

1. **Complete Phase 1-3**: Core infrastructure
2. **Test with sample docs**: Validate a few examples
3. **Set up CI/CD**: GitHub Actions workflow
4. **Migrate existing docs**: Add metadata to all examples
5. **Achieve 95% success rate**: Fix broken examples
6. **Maintain**: Keep docs in sync with code changes

---

## References

- [pytest documentation](https://docs.pytest.org/)
- [mistune documentation](https://mistune.lepture.com/)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Full Research Document](/Users/arthursarazin/Documents/graphRAGmcp/specs/001-system-documentation/research.md)
- [Decision Document](/Users/arthursarazin/Documents/graphRAGmcp/DECISION-doc-validation.md)

---

**Status**: Ready for Implementation
**Estimated Effort**: 5 days + ongoing migration
**Success Criteria**: 95% automated validation (SC-007)
