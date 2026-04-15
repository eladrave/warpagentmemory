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
    logger.info(f"Starting AgentMemory SSE MCP server natively on port {port}")
    
    # FastMCP SSE explicitly checks the host header against 'localhost' when it initializes its SSE connections
    # We must start the app completely natively with Uvicorn and disable host-checks.
    
    # Grab the underlying starlette app.
    app = None
    try:
        app = mcp.get_asgi_app()
    except AttributeError:
        try:
            app = mcp._mcp_server.get_asgi_app()
        except AttributeError:
            app = mcp._app
    
    import uvicorn
    import starlette.middleware.trustedhost
    
    # Nuke the trusted host middleware because GCP alters headers which causes 421s
    class DummyTrustedHostMiddleware:
        def __init__(self, app, allowed_hosts=None, **kwargs):
            self.app = app
        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)

    starlette.middleware.trustedhost.TrustedHostMiddleware = DummyTrustedHostMiddleware
    
    try:
        for i, mw in enumerate(app.user_middleware):
            if "TrustedHostMiddleware" in str(mw.cls):
                app.user_middleware[i] = starlette.middleware.Middleware(DummyTrustedHostMiddleware)
        app.middleware_stack = app.build_middleware_stack()
    except:
        pass
        
    # We run it manually. Uvicorn forwarded_allow_ips works best.
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
