import os
import logging
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context
from memory_manager import MemoryManager
from users import UserManager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

memory_manager = MemoryManager()
users_manager = UserManager()

# FastMCP creates its own Starlette app for SSE. 
# We'll just define the FastMCP instance, then attach our REST routes directly to its underlying Starlette app!
mcp = FastMCP("AgentMemory")

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
def add_memory(thingToRemember: str, ctx: Context) -> str:
    """
    Store user information, preferences, and behaviors. 
    Run on explicit commands or implicitly when detecting significant user traits.
    """
    try:
        token = get_token_from_ctx(ctx)
        memory_manager.add_memory(token, thingToRemember)
        return "Memory added successfully (queued for sync)."
    except Exception as e:
        return f"Error adding memory: {e}"

@mcp.tool()
def search_memory(informationToGet: str, ctx: Context) -> str:
    """
    Search user memories and patterns. 
    Run when explicitly asked or when context about user's past choices would be helpful.
    """
    try:
        token = get_token_from_ctx(ctx)
        results = memory_manager.search_memory(token, informationToGet)
        return results if results else "No relevant memories found."
    except Exception as e:
        return f"Error searching memory: {e}"

# --- REST API Endpoints attached to FastMCP's internal app ---

if __name__ == "__main__":
    # If run natively (e.g. from CLI without Starlette), run handles stdio by default.
    # Cloud run invokes `python server.py`, so we need to run SSE.
    port = int(os.getenv("PORT", "8080"))
    
    # We can start FastMCP in SSE mode. 
    # But wait, how do we add REST routes? FastMCP doesn't cleanly expose an add_route function in all versions.
    # Let's bypass creating custom REST endpoints inside the FastMCP server process.
    # Cloud Run deployments for MCP generally JUST serve MCP SSE. 
    # Our `cli.py` can just use MCP internally, or we can use a FastMCP.get_asgi_app() workaround if it exists.
    
    logger.info(f"Starting AgentMemory SSE MCP server on port {port}")
    mcp.run(transport="sse", host="0.0.0.0", port=port)
