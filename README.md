# AgentMemory

A robust AI Agent Memory system powered by Google Drive and Gemini File Search RAG.
It replicates the `supermemory-mcp` functionality but uses your own Google Drive and Gemini context window.

## Features
- **MCP Server (SSE):** Plugs into any agent using the `mcp` SDK to expose `add_memory` and `search_memory`.
- **Google Drive Storage:** Keeps your memories organized by day (`memory_YYYY-MM-DD.md`) and a synthesized `generic_memory.md`.
- **Gemini RAG Sync:** Automatically maintains a Gemini File Store containing your memories for high-speed, intelligent RAG retrieval.
- **Dreaming:** Periodically runs a background task to summarize daily memories into a concise `generic_memory.md` using Gemini.
- **CLI Interface:** Provides simple CLI commands to manually `add`, `search`, `sync --force`, and `dream`.
- **Rate-limit Safe:** Implements request debouncing, caching, and exponential backoff.

## Prerequisites
1. **Google Drive Service Account**: Needs `service_account.json` at the root of the project.
2. **Google Drive Folder**: Create a folder named exactly `AgentMemory` in your personal Google Drive and share it (with "Editor" permissions) to the email address found inside `service_account.json`.
3. **Gemini API Key**: Requires `GEMINI_API_KEY` defined in a `.env` file.

## Usage

### CLI
Install requirements:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Add a memory:
```bash
python cli.py add "I prefer dark mode in Warp."
```

Search your memory:
```bash
python cli.py search "What is my terminal theme preference?"
```

Force sync from Google Drive to Gemini:
```bash
python cli.py sync --force
```

Trigger the "dreaming" summarization manually:
```bash
python cli.py dream
```

### MCP Server
To run the SSE MCP Server (e.g. for cloud clients or local integrations via SSE):
```bash
python server.py
```
This will start a FastAPI server at `http://0.0.0.0:8000/mcp/sse`.

## Environment Variables
- `GEMINI_API_KEY`: Your Google Gemini API Key.
- `DREAMING_MODEL`: The model used for synthesizing memories (default: `gemini-2.5-flash`).
- `DREAM_INTERVAL_HOURS`: How often the background dreaming process should run (default: `24`).
- `PORT`: The port for the SSE FastMCP server (default: `8000`).

## Architecture
- `drive_api.py`: Manages the connection to Google Drive.
- `gemini_api.py`: Manages the Gemini File Search store and RAG retrieval.
- `memory_manager.py`: Combines Drive and Gemini with caching, debouncing, and background scheduling.
- `cli.py`: The command line interface.
- `server.py`: The FastMCP server.
