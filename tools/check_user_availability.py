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

def check_user_availability(email: str, start_time: str, end_time: str) -> dict:
    token = get_access_token()
    url = f"https://graph.microsoft.com/v1.0/users/{email}/calendar/getSchedule"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = {
        "schedules": [email],
        "startTime": {"dateTime": start_time, "timeZone": "Asia/Beirut"},
        "endTime": {"dateTime": end_time, "timeZone": "Asia/Beirut"},
        "availabilityViewInterval": 30
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code != 200:
        raise Exception(f"Graph API error: {response.status_code} - {response.text}")
    
    return response.json()

tool = {
    "name": "get_user_availability_graph",
    "description": "Get user's calendar availability",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "start_time": {"type": "string"},
            "end_time": {"type": "string"}
        },
        "required": ["email", "start_time", "end_time"]
    },
    "function": check_user_availability
}
