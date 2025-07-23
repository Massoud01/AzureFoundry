import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from msal import ConfidentialClientApplication
from mcp.server.fastmcp import FastMCP
from datetime import datetime
import pytz
import logging
from typing_extensions import Annotated

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def get_access_token() -> str:
    logging.info("Acquiring Azure AD token...")
    app = ConfidentialClientApplication(
        client_id=CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        error = result.get('error_description', 'Unknown error')
        logging.error(f"Failed to acquire token: {error}")
        raise Exception(f"Failed to acquire token: {error}")
    logging.info("Token acquired successfully.")
    return result["access_token"]


# Create MCP server instance
mcp = FastMCP("AvailabilityChecker")
logging.info("MCP Server instance created.")


@mcp.tool()
async def get_user_availability_graph(
    user_email: Annotated[str, "The email address of the user whose availability you want to check."],
    start_time: Annotated[str, "Start of the availability window in ISO 8601 format, e.g. 2025-07-22T10:00:00"],
    end_time: Annotated[str, "End of the availability window in ISO 8601 format, e.g. 2025-07-22T12:00:00"],
    time_zone: Annotated[str, "Time zone of the dates, e.g. Asia/Beirut"] = "Asia/Beirut",
) -> str:
    logging.info(f"Tool called: get_user_availability_graph with user_email={user_email}, start_time={start_time}, end_time={end_time}, time_zone={time_zone}")
    token = get_access_token()
    url = f"{GRAPH_API_ENDPOINT}/users/{user_email}/calendar/getSchedule"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body = {
        "schedules": [user_email],
        "startTime": {"dateTime": start_time, "timeZone": time_zone},
        "endTime": {"dateTime": end_time, "timeZone": time_zone},
        "availabilityViewInterval": 30,
    }
    def convert_utc_to_tz(utc_str: str, target_tz: str) -> str:
        dt_utc = datetime.fromisoformat(utc_str).replace(tzinfo=pytz.UTC)
        tz = pytz.timezone(target_tz)
        dt_tz = dt_utc.astimezone(tz)
        return dt_tz.strftime("%Y-%m-%d %H:%M:%S")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=body) as response:
            logging.info(f"Graph API response status: {response.status}")
            if response.status != 200:
                error_text = await response.text()
                logging.error(f"Failed to retrieve schedule: {response.status} - {error_text}")
                return f"❌ Failed to retrieve schedule: {response.status} - {error_text}"
            data = await response.json()
            schedule_items = data.get("value", [])[0].get("scheduleItems", [])

            if not schedule_items:
                msg = f"✅ {user_email} is available between {start_time} and {end_time} ({time_zone})."
                logging.info(msg)
                return msg

            busy_slots = "\n".join(
                f"{convert_utc_to_tz(item['start']['dateTime'], time_zone)} to {convert_utc_to_tz(item['end']['dateTime'], time_zone)}"
                for item in schedule_items
            )
            msg = f"⚠️ {user_email} is busy during these times (all shown in {time_zone} timezone):\n{busy_slots}"
            logging.info(msg)
            return msg

@mcp.tool()
async def create_calendar_event(
    user_email: Annotated[str, "The email of the user to create the event for."],
    subject: Annotated[str, "The subject of the event."],
    content: Annotated[str, "The content/body of the event."],
    start_time: Annotated[str, "Start datetime in ISO format, e.g. 2025-07-25T13:00:00"],
    end_time: Annotated[str, "End datetime in ISO format, e.g. 2025-07-25T14:00:00"],
    time_zone: Annotated[str, "Time zone for the event (e.g. Asia/Beirut)"] = "Asia/Beirut"
) -> dict:
    logging.info(f"Tool called: create_calendar_event for user={user_email}")
    token = get_access_token()
    url = f"{GRAPH_API_ENDPOINT}/users/{user_email}/events"

    event = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": content,
        },
        "start": {
            "dateTime": start_time,
            "timeZone": time_zone,
        },
        "end": {
            "dateTime": end_time,
            "timeZone": time_zone,
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=event) as response:
            logging.info(f"Graph API response status: {response.status}")
            if response.status != 201:
                error_data = await response.text()
                logging.error(f"Failed to create event: {response.status} - {error_data}")
                return {
                    "result": f"❌ Failed to create event: {response.status} - {error_data}",
                    "error": True
                }

            event_data = await response.json()
            logging.info("✅ Event created successfully.")
            return {
                "result": f"✅ Event '{subject}' created successfully for {user_email}.",
                "event_id": event_data.get("id"),
                "error": False
            }
        
if __name__ == "__main__":
    logging.info("Starting MCP Server...")
    print(mcp.run.__doc__)
    get_access_token() 
    mcp.run(transport="stdio") 
