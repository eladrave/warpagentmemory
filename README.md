# AgentMemory

A robust AI Agent Memory system powered by Google Drive and Gemini File Search RAG.
It replicates the `supermemory-mcp` functionality but uses your own Google Drive and Gemini context window.

## Features
- **MCP Server (SSE):** Plugs into any agent using the `mcp` SDK to expose `add_memory` and `search_memory`.
- **Multi-User Sync:** Each user gets their own auto-discovered Google Drive folder mapped to an API Token.
- **Google Drive Storage:** Keeps your memories organized by day (`memory_YYYY-MM-DD.md`) and a synthesized `generic_memory.md`.
- **Gemini RAG Sync:** Automatically maintains a Gemini File Store containing your memories for high-speed, intelligent RAG retrieval.
- **Dreaming:** Periodically runs a background task to summarize daily memories into a concise `generic_memory.md` using Gemini.
- **CLI Interface:** Provides simple CLI commands to manually `register`, `add`, `search`, `sync --force`, and `dream`.
- **Rate-limit Safe:** Implements request debouncing, caching, and exponential backoff.

## Prerequisites
1. **Google Drive Service Account**: Needs `service_account.json` at the root of the project.
2. **Gemini API Key**: Requires `GEMINI_API_KEY` defined in a `.env` file.

## Usage

### 1. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. User Registration
For a user to use this service, they must:
1. Create a folder in their personal Google Drive 
2. Share that folder with "Editor" permissions to the Service Account email.
3. The Admin runs the register command:
```bash
python cli.py register user@email.com
```
This generates an **API Token** (`am_...`) which is required for all future calls. The system will auto-discover the folder ID when that user adds a memory!

### 3. CLI Memory Commands
Add a memory:
```bash
python cli.py add --token am_abc123 "I prefer dark mode in Warp."
```

Search your memory:
```bash
python cli.py search --token am_abc123 "What is my terminal theme preference?"
```

Force sync from Google Drive to Gemini:
```bash
python cli.py sync --token am_abc123 --force
```

Trigger the "dreaming" summarization manually for all users:
```bash
python cli.py dream
```

### 4. MCP Server
To run the SSE MCP Server (e.g. for cloud clients or local integrations via SSE):
```bash
python server.py
```
This will start a FastAPI server at `http://0.0.0.0:8000/mcp/sse`. The connecting Agent must pass an `Authorization: Bearer am_abc123` header OR `?token=am_abc123` in the query params.

### 5. GCP Deployment
Deploy seamlessly to Google Cloud Run with GCS-mounted User Config:
```bash
./deploy.sh
```

## Architecture
- `users.py`: Flat JSON mapping `API_TOKEN -> email`.
- `drive_api.py`: Manages the connection to Google Drive and auto-discovers `AgentMemory` folders.
- `gemini_api.py`: Manages the Gemini File Search store and RAG retrieval.
- `memory_manager.py`: Combines Drive and Gemini with caching, debouncing, and background scheduling.
- `cli.py`: The command line interface.
- `server.py`: The FastMCP server.
