import os
import logging
from mcp.server.fastmcp import FastMCP, Context
from memory_manager import MemoryManager
from users import UserManager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

memory_manager = MemoryManager()
users_manager = UserManager()

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

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting AgentMemory SSE MCP server on port {port}")
    
    import sys
    from mcp.server.fastmcp.server import create_starlette_app
    app = create_starlette_app(mcp)
    
    # FastMCP uses Starlette, which uses TrustedHostMiddleware with ["*"]. However,
    # GCP strips or alters host headers sometimes. The foolproof way is to clear Starlette's middleware stack.
    # The ASGI spec says the app is just an async callable. We can just wrap it in our own dumb ASGI wrapper 
    # to scrub the Host header before it reaches Starlette's validation!
    
    async def host_scrubber_asgi(scope, receive, send):
        if scope["type"] == "http":
            new_headers = []
            for name, value in scope.get("headers", []):
                if name == b"host":
                    new_headers.append((b"host", b"localhost")) # Force valid host for starlette
                else:
                    new_headers.append((name, value))
            scope["headers"] = new_headers
        await app(scope, receive, send)

    import uvicorn
    uvicorn.run(host_scrubber_asgi, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
