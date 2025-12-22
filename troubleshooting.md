# Troubleshooting

## Railway Deployment Issues

### FastMCP.run() TypeError: unexpected keyword argument 'host'

**Problem:**
```
TypeError: FastMCP.run() got an unexpected keyword argument 'host'
```

**Cause:**
The MCP SDK 1.0+ changed the `FastMCP.run()` API. The `host` and `port` parameters are no longer accepted directly in the `run()` method for HTTP transport.

**Solution:**
Use `uvicorn` to run the ASGI app directly instead of relying on `mcp.run()`:

```python
# Before (broken in mcp>=1.0.0)
mcp.run(transport="streamable-http", host=args.host, port=args.port)

# After (works with mcp>=1.0.0)
import uvicorn
uvicorn.run(
    mcp.streamable_http_app(),
    host=args.host,
    port=args.port,
    log_level="info"
)
```

**Requirements:**
Add `uvicorn>=0.30.0` to `requirements.txt`.

**Date fixed:** 2025-12-22

---

### HTTP 421 "Invalid Host header" on Railway

**Problem:**
```
HTTP/2 421
Invalid Host header
```

**Cause:**
Railway uses a reverse proxy (railway-edge) to route requests. Uvicorn needs to be configured to trust proxy headers, otherwise it rejects requests with mismatched Host headers.

**Solution:**
Add proxy configuration to uvicorn:

```python
uvicorn.run(
    mcp.streamable_http_app(),
    host=args.host,
    port=args.port,
    log_level="info",
    proxy_headers=True,        # Trust X-Forwarded-* headers
    forwarded_allow_ips="*"    # Accept forwarded headers from any IP
)
```

**Date fixed:** 2025-12-22

---

### MCP SDK DNS Rebinding Protection (Invalid Host header)

**Problem:**
```
Invalid Host header (HTTP 421)
```

**Cause:**
MCP Python SDK 1.x introduced DNS rebinding protection. When deployed behind a reverse proxy (Railway, Cloud Run, etc.), the Host header doesn't match the allowed list.

**Solution:**
Disable DNS rebinding protection when Railway handles security at the edge:

```python
from mcp.server.transport_security import TransportSecuritySettings

transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

mcp = FastMCP("my_server", transport_security=transport_security)
```

**Reference:** https://github.com/modelcontextprotocol/python-sdk/issues/1798

**Date fixed:** 2025-12-22

---

### Pydantic Validation Error: "Field required" for params

**Problem:**
```
Error executing tool grand_debat_query: 1 validation error for grand_debat_queryArguments
params
  Field required [type=missing, input_value={'mode': 'global', 'query': '...', 'commune_id': 'Rochefort'}, input_type=dict]
```

**Cause:**
Tools defined with nested Pydantic models like `async def my_tool(params: MyModel)` expect clients to wrap arguments in a `params` object:
```json
{"params": {"commune_id": "X", "query": "Y"}}
```

But most MCP clients (including Dust.tt) send flat arguments:
```json
{"commune_id": "X", "query": "Y"}
```

**Solution:**
Use flat function parameters with `Annotated` types instead of nested Pydantic models:

```python
from typing import Annotated
from pydantic import Field

# Before (requires nested params - breaks Dust.tt)
class QueryInput(BaseModel):
    commune_id: str
    query: str

@mcp.tool()
async def my_tool(params: QueryInput) -> str:
    commune_id = params.commune_id
    ...

# After (accepts flat arguments - works with Dust.tt)
@mcp.tool()
async def my_tool(
    commune_id: Annotated[str, Field(description="Commune ID")],
    query: Annotated[str, Field(description="Query text")]
) -> str:
    # Use commune_id and query directly
    ...
```

**Date fixed:** 2025-12-22

---

### KeyError for Community ID (e.g., 'L0C3')

**Problem:**
```
ERROR:grand-debat-mcp:Query error for Saint_Jean_Dangely: 'L0C3'
```

**Cause:**
Some communes have 0 community reports (e.g., Saint_Jean_Dangely shows `Load KV community_reports with 0 data`). When the GraphRAG query tries to access community data by cluster ID, it fails because the community report doesn't exist.

The bug was in `nano_graphrag/_op.py` line 727: the code sorted all keys from `related_community_keys_counts` but some of those keys don't exist in `related_community_datas` (they were filtered out as None).

**Solution:**
Filter the sorted keys to only include those that exist in `related_community_datas`:

```python
# Before (crashes when community doesn't exist)
related_community_keys = sorted(
    related_community_keys_counts.keys(),
    ...
)

# After (safely handles missing communities)
related_community_keys = sorted(
    [k for k in related_community_keys_counts.keys() if k in related_community_datas],
    ...
)
```

**Date fixed:** 2025-12-22
