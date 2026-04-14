import os
import logging
import asyncio
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from memory_manager import MemoryManager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AgentMemory MCP Server")

memory_manager = MemoryManager()

mcp = FastMCP("AgentMemory")

@mcp.tool()
def add_memory(thingToRemember: str) -> str:
    """
    Store user information, preferences, and behaviors. 
    Run on explicit commands or implicitly when detecting significant user traits.
    """
    try:
        memory_manager.add_memory(thingToRemember)
        return "Memory added successfully (queued for sync)."
    except Exception as e:
        return f"Error adding memory: {e}"

@mcp.tool()
def search_memory(informationToGet: str) -> str:
    """
    Search user memories and patterns. 
    Run when explicitly asked or when context about user's past choices would be helpful.
    """
    try:
        results = memory_manager.search_memory(informationToGet)
        return results if results else "No relevant memories found."
    except Exception as e:
        return f"Error searching memory: {e}"

app.mount("/mcp", mcp.get_asgi_app())

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting AgentMemory SSE MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
