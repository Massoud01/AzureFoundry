import os
import time
import asyncio
import json
from dotenv import load_dotenv
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FunctionTool, MessageRole, ListSortOrder
from azure.identity import DefaultAzureCredential


# Clear console on start
os.system('cls' if os.name == 'nt' else 'clear')

# Load environment variables
load_dotenv()
project_endpoint = os.getenv("PROJECT_ENDPOINT")
model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")


async def connect_to_server(exit_stack: AsyncExitStack):
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],  # assumes server.py in same folder
        env=None,
    )

    # Start the MCP server subprocess and create client session
    stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
    stdio, write = stdio_transport

    session = await exit_stack.enter_async_context(ClientSession(stdio, write))
    await session.initialize()

    response = await session.list_tools()
    tools = response.tools
    print("\nConnected to MCP server with tools:", [tool.name for tool in tools])
    manual_result = await session.call_tool("get_user_availability_graph", {
    "user_email": "massoud.nohra@javistasandbox.onmicrosoft.com",
    "start_time": "2025-07-24T15:00:00",
    "end_time": "2025-07-24T15:30:00",
    "time_zone": "Asia/Beirut"
})
    print("Manual tool call result:", manual_result)


    return session


async def chat_loop(session):
    agents_client = AgentsClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(
            exclude_environment_credential=True,
            exclude_managed_identity_credential=True,
        ),
    )

    # Build async functions to call MCP tools
    response = await session.list_tools()
    tools = response.tools

    def make_tool_func(tool_name):
        async def tool_func(**kwargs):
            print(f"🔧 Calling tool '{tool_name}' with arguments:", kwargs, flush=True)
            result = await session.call_tool(tool_name, kwargs)
            print(f"✅ Tool '{tool_name}' returned:", result, flush=True)
            return result

        tool_func.__name__ = tool_name
        return tool_func

    functions_dict = {tool.name: make_tool_func(tool.name) for tool in tools}
    mcp_function_tool = FunctionTool(functions=list(functions_dict.values()))

    agent_id = "asst_R7aUwdnOcuNwdqNbu4ui3LZI"
#   agent = agents_client.create_agent(
#         model=model_deployment,
#         name="availability-agent",
#        instructions="""
# You are a helpful assistant that checks users' calendar availability using Microsoft Graph.
# To do this, use the tool 'get_user_availability_graph'.

# If the user message does not contain all required fields (user_email, start_time, end_time),
# you should ask the user for the missing information.

# Once all required fields are gathered, call the tool and return the result in a friendly way.
# """,

#         tools=mcp_function_tool.definitions,
#     )

    # Enable auto function calling for tools
    agents_client.enable_auto_function_calls(tools=mcp_function_tool)

    # Start a new chat thread
    thread = agents_client.threads.create()

    while True:
        user_input = input("Ask about availability (or type 'quit' to exit):\nUSER: ").strip()
        if user_input.lower() == "quit":
            print("Exiting chat.")
            break

        # Send user message to thread
        agents_client.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=user_input,
        )

        # Start agent run to process the message
        run = agents_client.runs.create(thread_id=thread.id, agent_id=agent_id)

        # Poll until run completes or fails or requires action
        while run.status in ["queued", "in_progress", "requires_action"]:
            time.sleep(1)
            run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)

            if run.status == "requires_action":
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    args_json = tool_call.function.arguments
                    print(f"Tool call: {function_name} with args: {args_json}")
                    raw_args = json.loads(args_json)


                    if "kwargs" in raw_args:
                        fixed_args = json.loads(raw_args["kwargs"])  # nested JSON string
                    else:
                        fixed_args = raw_args

                    print(f"🔧 Calling tool '{function_name}' with arguments: {fixed_args}")
                    if "email" in fixed_args and "user_email" not in fixed_args:
                        fixed_args["user_email"] = fixed_args.pop("email")

                    required_function = functions_dict.get(function_name)
                    output = await required_function(**fixed_args)
                    availability_msg = None
                    if hasattr(output, "structuredContent") and output.structuredContent:
                        availability_msg = output.structuredContent.get('result', None)
                    elif isinstance(output, dict):
                        availability_msg = output.get('result', None)
                    elif isinstance(output, str):
                        availability_msg = output  # fallback to string output
                            

                    tool_outputs.append(
                        {
                            "tool_call_id": tool_call.id,
                            "output": output if isinstance(output, str) else str(output),
                        }
                    )

                agents_client.runs.submit_tool_outputs(
                    thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs
                )

        if run.status == "failed":
            print(f"Run failed: {run.last_error}")
            continue

        # Retrieve and print agent messages in order
        messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        for message in messages:
            if message.text_messages:
                last_text = message.text_messages[-1].text.value
                print(f"{message.role}:\n{last_text}\n")


async def main():
    exit_stack = AsyncExitStack()
    try:
        session = await connect_to_server(exit_stack)
        await chat_loop(session)
    finally:
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())
