
import os
import json
import asyncio

from dotenv import load_dotenv
import httpx2

from mcp import Client
from mcp.client.streamable_http import streamable_http_client


# -----------------------------------------
# 1. Configuration
# -----------------------------------------

load_dotenv()

MCP_URL = "https://api.githubcopilot.com/mcp/"

GITHUB_TOKEN = (
    os.getenv("GITHUB_MCP_TOKEN")
    or os.getenv("GITHUB_TOKEN")
)

if not GITHUB_TOKEN:
    raise ValueError(
        "GITHUB_MCP_TOKEN or GITHUB_TOKEN "
        "is missing from your environment."
    )


# -----------------------------------------
# 2. Tool to inspect and call
# -----------------------------------------

# First run: leave TOOL_NAME as None.
# After viewing the available tools, enter
# the actual tool name and its arguments.

TOOL_NAME =  "get_file_contents"

TOOL_ARGUMENTS = {
    "owner": "aakashchauhan1712",
    "repo": "agentic-workbench",
    "path": "README.md"}


# -----------------------------------------
# 3. Connect to GitHub MCP
# -----------------------------------------

async def inspect_mcp():

    print("\nConnecting to GitHub MCP...")

    async with httpx2.AsyncClient(
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}"
        },
        timeout=300.0
    ) as http_client:

        transport = streamable_http_client(
            MCP_URL,
            http_client=http_client
        )

        async with Client(transport) as client:

            print("\nConnection successful!")

            # ---------------------------------
            # 4. Server metadata
            # ---------------------------------

            print("\n========== SERVER INFORMATION ==========")

            print("Server Info:")
            print(client.server_info)

            print("\nProtocol Version:")
            print(client.protocol_version)

            print("\nServer Capabilities:")
            print(client.server_capabilities)

            # ---------------------------------
            # 5. Discover available tools
            # ---------------------------------

            print("\n========== TOOLS LIST ==========")

            tools_result = await client.list_tools()

            for tool in tools_result.tools:

                print("\n---------------------------------")
                print("Tool Name:", tool.name)
                print("Title:", tool.title)
                print("Description:", tool.description)

                print("\nInput Schema:")

                print(
                    json.dumps(
                        tool.input_schema,
                        indent=4,
                        default=str
                    )
                )

                print("\nComplete Tool Metadata:")

                print(
                    json.dumps(
                        tool.model_dump(
                            mode="json",
                            exclude_none=True
                        ),
                        indent=4,
                        default=str
                    )
                )

            # ---------------------------------
            # 6. Execute an actual MCP tool
            # ---------------------------------

            if TOOL_NAME:

                print("\n========== TOOL CALL ==========")

                print("Calling:", TOOL_NAME)

                print("\nArguments:")

                print(
                    json.dumps(
                        TOOL_ARGUMENTS,
                        indent=4
                    )
                )

                result = await client.call_tool(
                    TOOL_NAME,
                    TOOL_ARGUMENTS
                )

                print("\n========== RAW TOOL RESULT ==========")

                print(
                    json.dumps(
                        result.model_dump(
                            mode="json",
                            exclude_none=True
                        ),
                        indent=4,
                        default=str
                    )
                )

                print("\n========== RESULT SUMMARY ==========")

                print("Is Error:", result.is_error)

                print("Structured Content:")
                print(result.structured_content)

                print("\nContent Blocks:")

                for block in result.content:

                    print("\nContent Type:", block.type)

                    if hasattr(block, "text"):
                        print("Text:", block.text)

                    elif hasattr(block, "mimeType"):
                        print("MIME Type:", block.mimeType)

            else:

                print(
                    "\nTool discovery completed. "
                    "Set TOOL_NAME and TOOL_ARGUMENTS "
                    "to execute a tool."
                )


# -----------------------------------------
# 7. Run
# -----------------------------------------

if __name__ == "__main__":
    asyncio.run(inspect_mcp())
