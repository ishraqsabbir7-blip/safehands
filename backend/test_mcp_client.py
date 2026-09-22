import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    url = "http://127.0.0.1:8000/mcp"

    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools (should show request_action, check_status)
            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools.tools])

            # Call request_action, like Alexa+ would
            result = await session.call_tool(
                "request_action",
                {"action": "pay_bill", "amount": 2500}
            )
            print("request_action result:", result.content)


asyncio.run(main())