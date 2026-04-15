import os
import logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context
from memory_manager import MemoryManager
from users import UserManager
from dotenv import load_dotenv

# --- Configuration & Logging ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AgentMemory")

app = FastAPI(title="AgentMemory MCP Server")

memory_manager = MemoryManager()
users_manager = UserManager()

mcp = FastMCP("AgentMemory")
mcp.settings.transport_security.enable_dns_rebinding_protection = False

def get_token_from_ctx(ctx: Context) -> str:
    try:
        if hasattr(ctx, "request_context") and ctx.request_context:
            req = getattr(ctx.request_context, "request", None)
            if req:
                auth_header = req.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    return auth_header.split(" ")[1]
                token_query = req.query_params.get("token")
                if token_query:
                    return token_query
    except Exception:
        pass
        
    test_token = os.getenv("TEST_TOKEN")
    if test_token:
        return test_token
    raise ValueError("Missing Authorization Bearer token or ?token= query parameter.")

# --- MCP Tools ---

@mcp.tool()
def add_memory(thingToRemember: str, token: str = None) -> str:
    """
    Store user information, preferences, and behaviors. 
    Run on explicit commands or implicitly when detecting significant user traits.
    """
    try:
        if not token:
            token = os.getenv("TEST_TOKEN")
        mem_id = memory_manager.add_memory(token, thingToRemember)
        return f"Memory [ID:{mem_id}] added successfully (queued for sync)."
    except Exception as e:
        return f"Error adding memory: {e}"

@mcp.tool()
def search_memory(informationToGet: str, token: str = None) -> str:
    """
    Search user memories and patterns. 
    Run when explicitly asked or when context about user's past choices would be helpful.
    """
    try:
        if not token:
            token = os.getenv("TEST_TOKEN")
        results = memory_manager.search_memory(token, informationToGet)
        return results if results else "No relevant memories found."
    except Exception as e:
        return f"Error searching memory: {e}"

@mcp.tool()
def get_all_memories(token: str = None) -> str:
    """
    Retrieve the entire memory store for the user. 
    Useful when you need a comprehensive overview of all past context or want to review everything.
    """
    try:
        if not token:
            token = os.getenv("TEST_TOKEN")
        return memory_manager.get_all_memories(token)
    except Exception as e:
        return f"Error fetching memories: {e}"

@mcp.tool()
def get_memories_by_time(start_date: str, end_date: str, token: str = None) -> str:
    """
    Retrieve all memories logged between two dates.
    Format for both start_date and end_date: YYYY-MM-DD
    Example: 2026-04-10
    """
    try:
        if not token:
            token = os.getenv("TEST_TOKEN")
        return memory_manager.get_memories_by_time(token, start_date, end_date)
    except Exception as e:
        return f"Error fetching memories by time: {e}"

@mcp.tool()
def delete_memory(memory_id: str, token: str = None) -> str:
    """
    Deletes a specific memory from the store.
    You must provide the exact 8-character memory_id (e.g. "abc12345") found via search or get_all tools.
    """
    try:
        if not token:
            token = os.getenv("TEST_TOKEN")
        return memory_manager.delete_memory(token, memory_id)
    except Exception as e:
        return f"Error deleting memory: {e}"

@mcp.tool()
def resync_memories(token: str = None) -> str:
    """
    Force a full re-sync of all local storage files to the Gemini RAG backend.
    Useful if memories were manually edited or bulk imported to the user's volume.
    """
    try:
        if not token:
            token = os.getenv("TEST_TOKEN")
        memory_manager.sync_force(token)
        return "Sync forced successfully."
    except Exception as e:
        return f"Error syncing memory: {e}"

@app.get("/")
def root():
    return {"status": "ok", "service": "AgentMemory"}

@app.get("/health")
def health():
    return {"status": "ok"}

# Mount FastMCP endpoint EXACTLY as driverag does
app.mount("/mcp", mcp.sse_app())
