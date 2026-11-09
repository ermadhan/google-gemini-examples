# Register a webhook for video-generation events.
# Based on https://github.com/google-gemini/cookbook/blob/main/quickstarts/Webhooks.ipynb
import os
from google import genai
from google.genai import errors, types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Set the GEMINI_API_KEY environment variable before running this script.")

client = genai.Client(api_key=GEMINI_API_KEY)

# Replace this URL with a receiver you control before creating a webhook.
WEBHOOK_ENDPOINT="https://gemini-webhook-receiver-670516618964.europe-west1.run.app/"

import requests

r = requests.get(WEBHOOK_ENDPOINT)
print(r.text)

import http.client
import json

# 1. Fill in your credentials
API_KEY = GEMINI_API_KEY 
CLOUD_RUN_URL = WEBHOOK_ENDPOINT  

# 2. Build payload structure
payload = {
    "subscribed_events": ["video.generated"],
    "name": "video_generation_webhook_v2",
    "uri": CLOUD_RUN_URL
}

# 3. Direct baseline socket mapping using the correct v1beta route
conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
headers = {"Content-Type": "application/json"}
target_path = f"/v1beta/webhooks?key={API_KEY}"

print("Sending REST execution target payload to v1beta...")

try:
    conn.request("POST", target_path, body=json.dumps(payload), headers=headers)
    response = conn.getresponse()
    response_data = response.read().decode()
    
    if response.status == 200:
        webhook_json = json.loads(response_data)
        
        # 🔑 Extracting the correct keys from the raw REST response dict
        signing_secret = webhook_json.get("secret")
        webhook_id = webhook_json.get("name") # Usually returns webhooks/id-string
        # The response can contain the signing secret; keep console output private.
        print(json.dumps(webhook_json, indent=2))
        print("\n✅ Webhook created completely!")
        print("--------------------------------------------------")
        print(f"🔑 WEBHOOK_SIGNING_SECRET: {signing_secret}")
        print(f"🆔 Webhook Resource ID: {webhook_id}")
        print("--------------------------------------------------")
        print("Copy the secret above and insert it into Cloud Run.")
    else:
        print(f"\n❌ API Returned Error Code: {response.status}")
        print(f"Details: {response_data}")
        
except Exception as e:
    print(f"\n❌ Script Execution Failed: {e}")
finally:
    conn.close()