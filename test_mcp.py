import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def run():
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env={"GEMINI_API_KEY": "AIzaSyAesf9swrBin2bBom2Vegvq9gAMUCUF8Hg", "TEST_TOKEN": "am_ef6f67db00b24c64857b1ba79bfe2c26"}
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("Listing tools...")
            tools = await session.list_tools()
            for t in tools.tools:
                print(f"- {t.name}: {t.description}")
                
            print("\nCalling search_memory...")
            res = await session.call_tool("search_memory", arguments={"informationToGet": "Does the user like Warp?"})
            print(res)

if __name__ == "__main__":
    asyncio.run(run())
