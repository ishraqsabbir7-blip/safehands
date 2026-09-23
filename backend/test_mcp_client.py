import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    url = "http://127.0.0.1:8000/mcp"

    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools.tools])

            # 1. Alexa+ requests the action
            result = await session.call_tool(
                "request_action",
                {"action": "pay_bill", "amount": 2500}
            )
            print("\n1. request_action:", result.content[0].text)

            challenge_id = json.loads(result.content[0].text)["challenge_id"]

            # 2. Phone approves it
            approve_result = await session.call_tool(
                "approve_pending",
                {"challenge_id": challenge_id}
            )
            print("\n2. approve_pending:", approve_result.content[0].text)

            # 3. Alexa+ checks status
            status_result = await session.call_tool(
                "check_status",
                {"challenge_id": challenge_id}
            )
            print("\n3. check_status:", status_result.content[0].text)


asyncio.run(main())