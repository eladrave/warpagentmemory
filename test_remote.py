import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
import httpx

async def run():
    url = "https://agentmemory-950783879036.us-central1.run.app/mcp/sse"
    print(f"Connecting to {url}...")
    
    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("Listing tools...")
            tools = await session.list_tools()
            for t in tools.tools:
                print(f"- {t.name}")
                
            print("\nCalling search_memory...")
            res = await session.call_tool("search_memory", arguments={"informationToGet": "Does the user like Warp?", "token": "am_ef6f67db00b24c64857b1ba79bfe2c26"})
            print(res)

if __name__ == "__main__":
    asyncio.run(run())
