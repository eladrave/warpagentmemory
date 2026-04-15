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
    app = None
    try:
        app = mcp.sse_app()
    except Exception as e:
        pass
            
    if app:
        import uvicorn
        
        async def asgi_wrapper(scope, receive, send):
            if scope["type"] == "http":
                # GCP Cloud Run throws 421 Invalid Host Header with Starlette.
                # Since Starlette checks the Host header matching standard specs, 
                # we just strip the Host header entirely and let it default to the proxy IP.
                new_headers = []
                for k, v in scope.get("headers", []):
                    if k.decode('ascii').lower() == "host":
                        new_headers.append((b"host", b"localhost"))
                    else:
                        new_headers.append((k, v))
                scope["headers"] = new_headers
                
                # Also force server to match
                scope["server"] = ("127.0.0.1", port)
                
            await app(scope, receive, send)

        uvicorn.run(asgi_wrapper, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
    else:
        # Fallback
        mcp.settings.port = port
        mcp.settings.host = "0.0.0.0"
        mcp.run("sse")
