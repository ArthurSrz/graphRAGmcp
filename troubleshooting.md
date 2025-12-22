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
