from tools.auth_config import TENANT_ID, CLIENT_ID, CLIENT_SECRET
from msal import ConfidentialClientApplication
import requests

def get_access_token():
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise Exception("❌ Failed to acquire access token.")
    return result["access_token"]

def create_calendar_event(email: str, subject: str, content: str, startDateTime: str, endDateTime: str, timeZone: str = "UTC") -> dict:
    token = get_access_token()
    url = f"https://graph.microsoft.com/v1.0/users/{email}/events"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": content},
        "start": {"dateTime": startDateTime, "timeZone": timeZone},
        "end": {"dateTime": endDateTime, "timeZone": timeZone}
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code >= 400:
        raise Exception(f"Graph API error: {response.status_code} - {response.text}")

    return response.json()

tool = {
    "name": "create_calendar_event",
    "description": "Create an Outlook calendar event for a user",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "subject": {"type": "string"},
            "content": {"type": "string", "default": ""},
            "startDateTime": {"type": "string"},
            "endDateTime": {"type": "string"},
            "timeZone": {"type": "string", "default": "UTC"}
        },
        "required": ["email", "subject", "startDateTime", "endDateTime"]
    },
    "function": create_calendar_event
}
