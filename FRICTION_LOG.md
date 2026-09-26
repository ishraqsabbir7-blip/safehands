Real problems we hit while building, in the order we hit them. Each entry follows: task attempted → steps taken → expected vs. actual → severity → workaround → suggestion.

1. mcp package v2 renamed FastMCP to MCPServer

Task attempted: Import FastMCP from the mcp Python SDK to build a "hello world" MCP server, following the pattern shown in most tutorials and examples available at the time.

Steps taken:

python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("safehands")

Expected: The server initializes and we can start registering tools.

Actual: ModuleNotFoundError: No module named 'mcp.server.fastmcp'. The error message itself explained that mcp v2.x renamed FastMCP to MCPServer and moved it to mcp.server.mcpserver, deprecating the standalone HTTP+SSE transport in favor of Streamable HTTP.

Severity: Medium — blocked all further backend work until resolved, but the fix was quick once found.

Workaround: Updated the import and class name:

python
from mcp.server.mcpserver import MCPServer
mcp = MCPServer("safehands")

Everything else (@mcp.tool(), .run()) carried over unchanged.

Suggested fix: The pip install mcp command installs the latest major version by default with no visible warning that this is a breaking change from most existing tutorials. A version-pinned "getting started" guide, or a clearer changelog surfaced during pip install, would save new developers real time.

2. mcp client's streamable_http_client() yields 2 values, not 3

Task attempted: Write a standalone MCP client script to test our server, following an example that unpacked the context manager into three values.

Steps taken:

python
async with streamable_http_client(url) as (read, write, _):

Expected: Connects and returns a read stream, write stream, and a third value (seen in some examples online).

Actual: ValueError: not enough values to unpack (expected 3, got 2). In this SDK version, the context manager only yields (read_stream, write_stream).

Severity: Low — one-line fix once the error message was read carefully.

Workaround:

python
async with streamable_http_client(url) as (read, write):

Suggested fix: Same root cause as #1 — SDK version drift between what's documented/tutorialized online versus the currently installed version. Clear versioned examples in the official docs would help.

3. Cross-language signature mismatch: JS and Python format floats differently

Task attempted: Sign a challenge in the browser (JavaScript, WebCrypto) and verify it on the server (Python, cryptography library), where both sides build the same message string before signing/verifying.

Steps taken: Both sides interpolated challenge.amount directly into a string:

Python: f"{challenge['amount']}" → produced "2500.0" (since MongoDB stores it as a float)
JavaScript: `${challenge.amount}` → produced "2500" (JSON parsing drops the trailing .0 for whole-number floats)

Expected: Both sides sign/verify against the exact same message bytes.

Actual: Signature verification failed with "Invalid signature" even when no actual tampering occurred, because the two languages formatted the same number differently, so the signed message didn't match the verified message byte-for-byte.

Severity: High — this looked exactly like a security bug (silently rejecting valid signatures) rather than a formatting bug, and took real debugging time to isolate.

Workaround: Explicitly formatted the amount to a fixed 2 decimal places on both sides before building the message:

Python: f"{float(challenge['amount']):.2f}"
JavaScript: Number(challenge.amount).toFixed(2)

Suggested fix: Any tutorial or reference implementation combining WebCrypto-signed payloads with a non-JS backend should call this out explicitly — cross-language numeric string formatting is an easy, silent way to break signature verification.

4. MongoDB auto-generated ObjectId broke JSON serialization silently

Task attempted: Return audit log entries from a Flask endpoint (GET /api/audit-log) as JSON for the dashboard to display.

Steps taken:

python
entries = list(audit_log.find(sort=[("seq", 1)]))
return jsonify(entries)

(We had not set a custom _id for audit log documents, unlike the challenges collection where we deliberately used a UUID string.)

Expected: A JSON array of log entries.

Actual: The request failed server-side because jsonify() doesn't know how to serialize MongoDB's auto-generated ObjectId. On the frontend, this surfaced as a silent failure — no crash, no visible error, the dashboard's audit log and "Chain Verified" status simply never updated, because our fetchLog() function had no error handling.

Severity: Medium — not a security issue, but genuinely hard to notice since nothing crashed or logged an obvious error.

Workaround: Excluded _id from the query projection, since we don't use it for audit log entries anyway (we use our own seq field as the identifier):

python
entries = list(audit_log.find({}, {"_id": 0}, sort=[("seq", 1)]))

Suggested fix: For our own future projects — always wrap frontend fetch calls in try/catch so failures are visible rather than silent. This is a good general lesson about defensive coding on the frontend, not specifically an SDK/tool issue.

General note

We're running Python 3.14.3 throughout this project — a very recent release — and all core dependencies (mcp, cryptography, flask, pymongo) installed and worked without compatibility issues, which was a pleasant surprise given how new the interpreter is.