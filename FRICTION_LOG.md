- mcp package v2.0: FastMCP renamed to MCPServer, moved from
  mcp.server.fastmcp to mcp.server.mcpserver. Fixed by updating the
  import and class name; usage (@mcp.tool(), .run()) unchanged.
  Source: https://py.sdk.modelcontextprotocol.io/v2/migration/
  - Running backend/mcp_server.py directly failed with
  "ModuleNotFoundError: No module named 'backend'" because Python adds
  the script's own folder to sys.path, not the project root.
  Fixed by running as a module instead: python -m backend.mcp_server
  - mcp client: streamable_http_client() context manager yields
  (read_stream, write_stream) — 2 values, not 3 as in some older
  examples. Fixed by unpacking only 2.