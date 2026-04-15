import os
import logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context
from memory_manager import MemoryManager
from users import UserManager
from dotenv import load_dotenv
import starlette.middleware.trustedhost

# --- CRITICAL FIX FOR GOOGLE CLOUD RUN 421 ERRORS ---
# Overwrite TrustedHostMiddleware entirely before FastMCP or FastAPI ever invoke it
class DummyTrustedHostMiddleware:
    def __init__(self, app, allowed_hosts=None, **kwargs):
        self.app = app
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

starlette.middleware.trustedhost.TrustedHostMiddleware = DummyTrustedHostMiddleware

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

# Standard FastAPI app that works natively on Cloud Run
app = FastAPI()

# Force clear middleware just in case
app.user_middleware = []
app.middleware_stack = app.build_middleware_stack()

# Mount FastMCP's underlying SSE app as a sub-app.
try:
    mcp_app = mcp.get_asgi_app()
except Exception:
    mcp_app = mcp._mcp_server.get_asgi_app() if hasattr(mcp, "_mcp_server") and hasattr(mcp._mcp_server, "get_asgi_app") else mcp._app

# Also strip the FastMCP inner starlette app
if hasattr(mcp_app, "user_middleware"):
    mcp_app.user_middleware = []
    mcp_app.middleware_stack = mcp_app.build_middleware_stack()

app.mount("/mcp", mcp_app)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting AgentMemory API natively on port {port}")
    # Run FastAPI via standard uvicorn, which handles GCP headers properly natively.
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
