# AgentMemory

A robust AI Agent Memory system powered by Gemini File Search RAG and Google Cloud Storage.
It replicates the `supermemory-mcp` functionality using your own Gemini context window and allows you to host an independent remote memory server on Google Cloud Run.

This system is built from the ground up to solve the `421 Invalid Host Header` bugs common when running Starlette/FastMCP servers behind Google Cloud Load Balancers, by strictly wrapping FastMCP inside a standard FastAPI + Uvicorn deployment.

## Features
- **MCP Server (SSE):** Plugs into any agent (like Warp or Claude Desktop) using the `mcp` SDK.
- **Full CRUD Tools:** Exposes `add_memory`, `search_memory`, `get_all_memories`, `get_memories_by_time`, `delete_memory`, and `resync_memories`.
- **Multi-User Sync:** Each user gets their own isolated memory instance via an API Token.
- **Local / GCS Storage:** Keeps your memories organized by day (`memory_YYYY-MM-DD.txt`) and a synthesized `generic_memory.txt` on a mounted GCS volume, ensuring state is preserved across container restarts without databases.
- **Gemini RAG Sync:** Automatically maintains a Gemini File Store containing your memories for high-speed, intelligent RAG retrieval.
- **Dreaming:** Periodically runs a background task to summarize daily memories into a concise `generic_memory.txt` using Gemini.
- **CLI Interface:** Provides simple CLI commands to manually `register`, `add`, `search`, `sync --force`, and `dream`.
- **Latency Protected:** Searches actively scan both Gemini *and* your unindexed local buffer to prevent data loss during Gemini's indexing delays.

## Prerequisites
1. **Google Cloud Account**: Required if deploying to Cloud Run.
2. **Gemini API Key**: Required for the embedding and RAG processes. Define this in a `.env` file as `GEMINI_API_KEY`.

---

## 🚀 Quickstart & Usage

### 1. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. User Registration (Admin)
Before anyone can use the server, an admin must register their email. 
```bash
python cli.py register yourname@email.com
```
This generates an **API Token** (`am_...`) which is required for all future calls. 

### 3. Deploy to Google Cloud Run
Deploying the MCP Server is handled cleanly by the provided script. It will create a Google Cloud Storage bucket to hold your `users.json` and memory markdown files, mount it via Cloud Storage FUSE, and deploy the server.
```bash
./deploy.sh
```
*Note: Make sure to add your `GEMINI_API_KEY` to the Cloud Run service secrets/environment variables in the GCP Console after deploying.*

---

## 🤖 Adding AgentMemory to your AI Agents

Because AgentMemory is fully compliant with the Model Context Protocol (MCP), you can add it to any supported agentic software.

### Important: Autonomous Memory Configuration
In `skills/agentmemory/SKILL.md` we provide an out-of-the-box instruction set that forces your agent to **proactively save and retrieve** facts without you ever explicitly telling it to "remember" something. 
Copy that `SKILL.md` into your agent's skills directory!

### Example 1: Warp Terminal 
You can add AgentMemory as an MCP server in Warp by adding the deployed Cloud Run SSE URL to your configuration, or by running it locally using `stdio`.

**If running locally via Stdio:**
```json
{
  "mcpServers": {
    "agentmemory": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/server.py"],
      "env": {
        "AGENTMEMORY_TOKEN": "am_YOUR_GENERATED_TOKEN",
        "GEMINI_API_KEY": "AIzaSy..."
      }
    }
  }
}
```

**If connecting to your Remote Cloud Run Server (SSE):**
Agents connecting over HTTP/SSE must pass their token as a tool argument when invoking the server.
You should provide your agent with the following system instructions or load the provided `SKILL.md` file:
> "When remembering or recalling facts, use the AgentMemory tools. You MUST pass the token `am_YOUR_GENERATED_TOKEN` in the `token` argument."

### Example 2: Claude Desktop
Add the following to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "agentmemory": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/server.py"],
      "env": {
        "AGENTMEMORY_TOKEN": "am_YOUR_GENERATED_TOKEN",
        "GEMINI_API_KEY": "AIzaSy..."
      }
    }
  }
}
```

---

## 🛠️ CLI Manual Commands

You can manually interact with your memory store via the CLI:

**Add a memory:**
```bash
python cli.py add --token am_abc123 "I prefer dark mode in Warp."
```

**Search your memory:**
```bash
python cli.py search --token am_abc123 "What is my terminal theme preference?"
```

**Force sync from Storage to Gemini:**
```bash
python cli.py sync --token am_abc123 --force
```

**Trigger the "dreaming" summarization manually for all users:**
```bash
python cli.py dream
```

---

## 🏗️ Architecture & Development Notes
For a deep dive into why this application is structured the way it is—including how we bypassed the `421 Invalid Host Header` bugs in standard Starlette/FastMCP deployments—please read the `AGENTS.md` file included in this repository. 
