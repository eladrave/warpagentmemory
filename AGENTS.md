# AgentMemory Architecture & Developer Guide

## Overview
AgentMemory is an AI Memory storage system modeled after `supermemory-mcp`, designed to be used as a remote Model Context Protocol (MCP) server running on Google Cloud Run. It enables multiple AI agents (like Warp, Opencode, Claude Desktop) to persistently "remember" user preferences by storing them as text and indexing them via Google Gemini File Search RAG.

## The Cloud Run / FastMCP Architecture Problem
We faced severe, compounding architecture failures when trying to deploy this simple system to Google Cloud Run natively.

### 1. The Google Drive API Limitation
Initially, we wanted the system to write `.md` files directly to a user's Google Drive. However, the system runs under a Google Cloud Service Account.
**The Trap:** GCP Service Accounts have exactly `0 bytes` of storage quota in standard Google Drive. While they can *read* from standard user folders, any file they *create* inside a user's folder technically belongs to the SA, immediately triggering a `403 storageQuotaExceeded` error.
**The Solution:** We abandoned Google Drive entirely for writing files. Instead, the application mounts a Google Cloud Storage (GCS) bucket using Cloud Run FUSE (to `/mnt/gcs/`). We read/write all `.txt` memory files locally on this mount, which persists safely across container restarts, and upload those directly to the Gemini Corpus.

### 2. The FastMCP / Starlette Host Header `421` Bug
FastMCP uses Starlette for its Server-Sent Events (SSE) backend. When Starlette runs behind Google Cloud Load Balancers (like in Cloud Run), the `Host` headers are altered. Starlette's `TrustedHostMiddleware` immediately rejects these requests with a fatal `421 Invalid Host header` error.
**The Trap:** We attempted to monkey-patch `TrustedHostMiddleware`, replace the ASGI app, and write custom FastAPI wrapper mounts to strip the headers. All of these failed or caused `500 Internal Server Errors` because the `mcp` SDK handles its ASGI sub-app extraction inconsistently across versions.
**The Solution:** We completely abandoned custom fastmcp configurations and ASGI hacking. We replicated the `driverag` deployment structure perfectly:
1. Instantiate a standard `FastAPI` app.
2. Initialize `FastMCP` and mount its `sse_app()` output directly onto the FastAPI instance: `app.mount("/mcp", mcp.sse_app())`.
3. Start the server using the standard `uvicorn` CLI (via the Dockerfile `CMD`), passing `--proxy-headers` and `--forwarded-allow-ips *` flags. This allows Uvicorn to natively handle the GCP Load Balancer headers correctly before they ever reach FastMCP's internal Starlette validation.

### 3. The FastMCP Context Loss Bug
FastMCP's `Context` object `ctx.request_context.request.headers` does not reliably persist HTTP headers (like `Authorization: Bearer <token>`) during RPC tool execution over an active SSE stream. 
**The Trap:** If you try to extract the User Token from the HTTP request context inside the `@mcp.tool()` function, it will randomly throw `ValueError: Missing token`.
**The Solution:** Do not rely on HTTP Headers for tool authentication. We modified the tool definitions to explicitly require the token as an argument:
`def add_memory(thingToRemember: str, token: str) -> str:`
The MCP client must pass this token natively in the JSON-RPC payload.

### 4. Gemini `.md` File Rejection
The Google `genai` File Search API will periodically reject `.md` files during corpus uploads, claiming `Unknown mime type`.
**The Solution:** We enforce `.txt` file extensions (`memory_YYYY-MM-DD.txt`) for all disk writes and Gemini uploads.

## How the Application Operates Now
- **Users**: We store a flat mapping of `API_TOKEN -> email` inside `users.json` on the GCS mount. The CLI `python cli.py register <email>` handles this.
- **Tools**: The `@mcp.tool()` handlers accept the user's explicit token as an argument, resolve the email, and pass the data to `MemoryManager`.
- **Buffering**: `MemoryManager` buffers memory additions locally and flushes them to the GCS mount and Gemini every 15 seconds to prevent Gemini rate limit exceptions.
- **Latency Protection**: Since Gemini RAG takes ~10 seconds to index an uploaded file, the `search_memory` tool dynamically reads the raw, unindexed content of *today's* text file from the GCS mount and injects it directly into the Gemini LLM system instruction alongside the RAG tool. This guarantees immediate memory recall.

## Deployment
```bash
./deploy.sh
```
This provisions the GCS bucket (`<project>-agentmemory-users`), mounts it, and deploys `server:app` via Uvicorn to Cloud Run.

### New CRUD Capabilities
As of the latest updates, this system supports full CRUD operations on Agent Memory. 
When an agent calls `add_memory`, the system explicitly generates an 8-character ID and prepends it to the memory string (e.g. `[ID: a1b2c3d4]`). 

When an agent needs to perform management tasks on the memory, they can use these new tools:
- `get_all_memories(token)`: Dumps the entire history.
- `get_memories_by_time(start_date, end_date, token)`: Filters memories between `YYYY-MM-DD` strings.
- `delete_memory(memory_id, token)`: Scans all local `.txt` files for `[ID: memory_id]`, deletes the line from the local file, rewrites it, and forces a Gemini resync.
- `resync_memories(token)`: Useful if an agent or user manually imports `.txt` files directly to the GCS volume. This drops the existing Gemini corpus and uploads all files synchronously.

### Proactive Skill Injection
Agents using this system are heavily prompted via `SKILL.md` to be extremely proactive. They are instructed to silently run `add_memory` on their own volition anytime they discover facts or preferences about the user, and to proactively run `search_memory` when a user asks a context-heavy question, ensuring long-term continuity without explicit user instruction.
