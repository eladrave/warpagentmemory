name: agentmemory
description: Proactively persist user preferences, context, and facts into the remote AgentMemory store using the user's API Token, or recall them. Agents must use this skill continuously to build a profile of the user and fetch past knowledge.

# AgentMemory Instruction Manual

As an AI Agent, you are connected to the `agentmemory` MCP Server. You should use this system as a long-term memory store to remember facts about the user, their environment, their coding preferences, constraints, project histories, and workflows.

## Initialization & Setup (Agent Instructions)
If the `agentmemory` MCP server is **not** currently running or available in your list of connected tools, you must immediately take the following actions to set it up for the user:

1. **Check Environment**: Determine what agentic environment you are running in (e.g. Warp, Claude Desktop, Cursor). 
2. **Prompt the User**: Ask the user for the following two credentials necessary to configure the server locally:
   - **`AGENTMEMORY_TOKEN`**: The API token generated for their email.
   - **`GEMINI_API_KEY`**: Their Google Gemini API Key.
   - *(Note: If they do not have an AGENTMEMORY_TOKEN, inform them they must run `python cli.py register <their-email>` inside the `agentmemory` repository first).*
3. **Configure the Server**: Once the user provides the keys, locate their MCP configuration file (e.g. `claude_desktop_config.json` or by invoking the Warp MCP config builder).
4. **Write the Config**: Insert the following JSON block into their MCP Server configuration. Replace `/path/to/...` with the actual absolute path to the `agentmemory` repository on their machine:
```json
{
  "mcpServers": {
    "agentmemory": {
      "command": "/path/to/agentmemory/venv/bin/python",
      "args": ["/path/to/agentmemory/server.py"],
      "env": {
        "AGENTMEMORY_TOKEN": "am_YOUR_API_TOKEN",
        "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY"
      }
    }
  }
}
```
5. **Restart**: Inform the user they may need to restart their agent or client to load the new MCP server.

## IMPORTANT: Proactive Usage

Once connected, you **MUST** use these tools proactively. You do NOT need to wait for the user to say "remember this". 
- If the user mentions a preference (e.g. "I use `zsh`" or "I prefer to use React Router v7"), silently call `add_memory` to store it.
- If the user corrects a mistake you made (e.g. "No, in this codebase we use `snake_case` for endpoints"), call `add_memory` to store that correction so you don't repeat it in the future.
- If the user asks a question about past projects, configurations, or personal details, proactively call `search_memory` to fetch the context *before* answering.

## Using the Tools

You have access to a full CRUD suite of tools for managing memory:

1. **`add_memory(thingToRemember: str, token: str)`**
   - Automatically prepends an 8-character `[ID: xxx]` to the memory.
   
2. **`search_memory(informationToGet: str, token: str)`**
   - Executes a RAG search across the user's memory files. Returns relevant facts and their associated `[ID: xxx]`.

3. **`get_all_memories(token: str)`**
   - Dumps the entire history of memory `.txt` files. Useful for auditing or massive context gathering.

4. **`get_memories_by_time(start_date: str, end_date: str, token: str)`**
   - Fetch all memories from a specific date range (`YYYY-MM-DD`).

5. **`delete_memory(memory_id: str, token: str)`**
   - If a memory is obsolete or wrong, use `search_memory` or `get_all_memories` to find its 8-character ID, then call this tool to delete it permanently.

6. **`resync_memories(token: str)`**
   - Force a hard upload of all local `.txt` memories back into the Gemini RAG backend.

**Note:** Always pass the user's token (e.g. `am_ef6f67db00b24c64857b1ba79bfe2c26`) into the `token` argument of these tools! If you don't know it, check your environment variables (like `AGENTMEMORY_TOKEN`) or ask the user.
