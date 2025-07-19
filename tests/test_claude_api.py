import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

if not ANTHROPIC_API_KEY:
    raise EnvironmentError("ANTHROPIC_API_KEY not set in environment variables or .env file.")

headers = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}

payload = {
    "model": ANTHROPIC_MODEL,
    "max_tokens": 100,
    "messages": [
        {"role": "user", "content": "Hello Claude! Reply with just the word OK."}
    ]
}

response = requests.post(ANTHROPIC_API_URL, headers=headers, data=json.dumps(payload))

print("Status code:", response.status_code)
print("Response:")
print(response.text)
