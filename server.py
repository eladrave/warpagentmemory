import os
import logging
from mcp.server.fastmcp import FastMCP, Context
from memory_manager import MemoryManager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

memory_manager = MemoryManager()

# Let FastMCP handle the server fully.
# We will use stdio by default, but FastMCP supports SSE automatically.
mcp = FastMCP("AgentMemory")

def get_token_from_ctx(ctx: Context) -> str:
    try:
        # In typical mcp setups, the query parameter or header might be injected into request_context
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
        
    # As a fallback for stdio/local testing without proper auth injection:
    test_token = os.getenv("TEST_TOKEN")
    if test_token:
        return test_token
    raise ValueError("Missing Authorization Bearer token or ?token= query parameter.")

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

if __name__ == "__main__":
    # Start the FastMCP server, allowing it to determine transport (stdio vs SSE)
    port = int(os.getenv("PORT", "8000"))
    mcp.run()
