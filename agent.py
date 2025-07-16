from azure.ai.foundry.agent import Agent


from tools.check_user_availability import tool as check_availability_tool
from tools.create_calendar_event import tool as create_event_tool


agent = Agent(
    name="Calendar Management Agent",
    instructions="You are a helpful assistant that can check calendar availability and book events via Microsoft Graph.",
    description="Agent for managing calendars using Microsoft Graph tools.",
    tools=[
        check_availability_tool,
        create_event_tool,
    ],
)


__agent__ = agent
