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
        memory_manager.add_memory(token, thingToRemember)
        return "Memory added successfully (queued for sync)."
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

@app.get("/")
def root():
    return {"status": "ok", "service": "AgentMemory"}

@app.get("/health")
def health():
    return {"status": "ok"}

# Mount FastMCP endpoint EXACTLY as driverag does
app.mount("/mcp", mcp.sse_app())
