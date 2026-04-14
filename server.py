import os
import logging
import asyncio
from fastapi import FastAPI, Depends, Request
from mcp.server.fastmcp import FastMCP, Context
from memory_manager import MemoryManager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AgentMemory MCP Server")

memory_manager = MemoryManager()

# Instead of passing `Context` which FastMCP strips or fails on depending on version,
# we intercept requests before FastMCP and extract the token into the FastMCP session's state/context if possible,
# OR we use HTTP headers. FastMCP tools receive Context, which has `request_context`.
mcp = FastMCP("AgentMemory")

def get_token_from_ctx(ctx: Context) -> str:
    try:
        # In recent FastMCP versions, Context.request_context is available.
        # This is populated by Starlette/FastAPI underneath.
        req = getattr(ctx.request_context, "request", None)
        if not req:
            raise ValueError("No request object found in context.")
            
        auth_header = req.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.split(" ")[1]
            
        token_query = req.query_params.get("token")
        if token_query:
            return token_query
            
        raise ValueError("Missing Authorization Bearer token or ?token= query parameter.")
    except Exception as e:
        logger.error(f"Failed to get token: {e}")
        # As a fallback for local testing without proper auth injection:
        test_token = os.getenv("TEST_TOKEN")
        if test_token:
            return test_token
        raise ValueError("No valid token provided.")

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

app.mount("/mcp", mcp.get_asgi_app())

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting AgentMemory SSE MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
