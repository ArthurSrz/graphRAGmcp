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
