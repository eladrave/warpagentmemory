# AgentMemory

A robust AI Agent Memory system powered by Gemini File Search RAG and Google Cloud Storage.
It replicates the `supermemory-mcp` functionality using your own Gemini context window.

## Features
- **MCP Server (Stdio & SSE):** Plugs into any agent using the `mcp` SDK to expose `add_memory` and `search_memory`.
- **Multi-User Sync:** Each user gets their own memory isolated via an API Token.
- **Local / GCS Storage:** Keeps your memories organized by day (`memory_YYYY-MM-DD.txt`) and a synthesized `generic_memory.txt` on a mounted GCS volume, bypassing strict Google Drive SA quotas.
- **Gemini RAG Sync:** Automatically maintains a Gemini File Store containing your memories for high-speed, intelligent RAG retrieval.
- **Dreaming:** Periodically runs a background task to summarize daily memories into a concise `generic_memory.md` using Gemini.
- **CLI Interface:** Provides simple CLI commands to manually `register`, `add`, `search`, `sync --force`, and `dream`.
- **Rate-limit Safe:** Implements request debouncing, caching, and exponential backoff.

## Prerequisites
1. **Gemini API Key**: Requires `GEMINI_API_KEY` defined in a `.env` file.

## Usage

### 1. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. User Registration
For a user to use this service, the Admin runs the register command:
```bash
python cli.py register user@email.com
```
This generates an **API Token** (`am_...`) which is required for all future calls. 

### 3. CLI Memory Commands
Add a memory:
```bash
python cli.py add --token am_abc123 "I prefer dark mode in Warp."
```

Search your memory:
```bash
python cli.py search --token am_abc123 "What is my terminal theme preference?"
```

Force sync from Storage to Gemini:
```bash
python cli.py sync --token am_abc123 --force
```

Trigger the "dreaming" summarization manually for all users:
```bash
python cli.py dream
```

### 4. MCP Server
If you are running the MCP server locally using `stdio`, you can pass the API Token using the `TEST_TOKEN` environment variable in your agent's config:
```json
{
  "mcpServers": {
    "agentmemory": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {
        "TEST_TOKEN": "am_abc123",
        "GEMINI_API_KEY": "AIzaSy..."
      }
    }
  }
}
```

If deployed remotely using SSE, the connecting Agent must pass an `Authorization: Bearer am_abc123` header OR `?token=am_abc123` in the query params.

### 5. GCP Deployment
Deploy seamlessly to Google Cloud Run with GCS-mounted User Config & Memories:
```bash
./deploy.sh
```

## Architecture
- `users.py`: Flat JSON mapping `API_TOKEN -> email`.
- `gemini_api.py`: Manages the Gemini File Search store and RAG retrieval.
- `memory_manager.py`: Combines GCS/Local storage and Gemini with caching, debouncing, and background scheduling.
- `cli.py`: The command line interface.
- `server.py`: The FastMCP server.
