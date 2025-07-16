import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config.json")

with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

TENANT_ID = CONFIG["TENANT_ID"]
CLIENT_ID = CONFIG["CLIENT_ID"]
CLIENT_SECRET = CONFIG["CLIENT_SECRET"]
