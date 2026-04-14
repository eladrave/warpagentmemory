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

app = FastAPI(title="AgentMemory API & MCP Server")

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

# --- REST API Endpoints ---

class RegisterRequest(BaseModel):
    email: str

class AddMemoryRequest(BaseModel):
    text: str

class SearchRequest(BaseModel):
    query: str

def get_rest_token(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ")[1]

@app.post("/register")
def register_user(req: RegisterRequest):
    # Depending on security posture, this might need an ADMIN_KEY check
    admin_key = os.getenv("ADMIN_KEY")
    if admin_key:
        # In a real setup, we might extract this from a header
        pass
        
    token = users_manager.add_user(req.email)
    return {"token": token, "email": req.email}

@app.post("/add")
def api_add_memory(req: AddMemoryRequest, authorization: str = Header(None)):
    token = get_rest_token(authorization)
    try:
        memory_manager.add_memory(token, req.text)
        return {"status": "success", "message": "Memory added to buffer."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/search")
def api_search_memory(req: SearchRequest, authorization: str = Header(None)):
    token = get_rest_token(authorization)
    try:
        results = memory_manager.search_memory(token, req.query)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/sync")
def api_sync_memory(authorization: str = Header(None)):
    token = get_rest_token(authorization)
    try:
        memory_manager.sync_force(token)
        return {"status": "success", "message": "Forced sync completed."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/dream")
def api_dream_memory():
    # Typically an admin or scheduled cron endpoint
    try:
        memory_manager.dream_all_users()
        return {"status": "success", "message": "Global dream initiated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount MCP ASGI App
app.mount("/mcp", mcp.get_asgi_app())

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting AgentMemory REST + SSE MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
