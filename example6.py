import http.client
import json
import os
import sys

# 1. Provide your configuration targets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Set the GEMINI_API_KEY environment variable before running this script.")

WEBHOOK_ENDPOINT="https://gemini-webhook-receiver-670516618964.europe-west1.run.app/"

# 2. Open standard secure socket to Gemini endpoint gateway
conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
target_path = f"/v1beta/webhooks?key={GEMINI_API_KEY}"

print("Fetching project webhook inventory from v1beta...")

try:
    # 3. Fire a GET request to pool all registered webhooks
    conn.request("GET", target_path)
    response = conn.getresponse()
    response_data = response.read().decode()
    
    if response.status == 200:
        data = json.loads(response_data)
        all_webhooks = data.get("webhooks", [])
        
        print(f"\nFound {len(all_webhooks)} total webhooks in this project.")
        print("--------------------------------------------------")
        
        # 4. Loop over configuration objects and filter matches locally
        matching_count = 0
        for wh in all_webhooks:
            wh_uri = wh.get("uri")
            
            if wh_uri == WEBHOOK_ENDPOINT:
                matching_count += 1
                print(f"🎯 Match #{matching_count}:")
                print(f"   Resource Name : {wh.get('name')}")
                print(f"   Unique ID     : {wh.get('id')}")
                print(f"   Active State  : {wh.get('state')}")
                print(f"   Subscribed To : {wh.get('subscribed_events')}")
                print("--------------------------------------------------")
                
        if matching_count == 0:
            print("❌ No active webhooks match that specific target URL.")
            
    else:
        print(f"\n❌ Fetch Failed with Status: {response.status}")
        print(f"Details: {response_data}")

except Exception as e:
    print(f"\n❌ Execution failure: {e}")
finally:
    conn.close()

from google import genai
from google.genai import errors
from google.genai._gaos.lib.compat_errors import GeminiNextGenAPIClientError
from google.genai.types import HttpOptions

client = genai.Client(
    api_key=  GEMINI_API_KEY,
    http_options=HttpOptions(api_version="v1beta")
)

# The response contains a page of webhooks; follow tokens to include all pages.
filtered_webhooks = []
page_token = None
while True:
    response = client.webhooks.list(page_token=page_token)
    filtered_webhooks.extend(
        wh for wh in (response.webhooks or []) if wh.uri == WEBHOOK_ENDPOINT
    )
    page_token = response.next_page_token
    if not page_token:
        break

print(f"SDK found {len(filtered_webhooks)} matching webhooks.")


webhooks = client.webhooks.list()
print(webhooks.model_dump_json(indent=2))


webhook_id = "i8g6br9yu104gax43fi95rqzjvr3yfofuyeb"
operation = "ping"
try:
    print("Pinging webhook...")
    print(client.webhooks.ping(id=webhook_id))

    operation = "get"
    wh = client.webhooks.get(id=webhook_id)
    print(wh)

    update = True
    if update:
        operation = "update"
        wh = client.webhooks.update(
            id=webhook_id,
            subscribed_events=["video.generated", "batch.succeeded"],
            name="video_and_batch_webhook",
        )

    delete = True
    if delete:
        operation = "delete"
        client.webhooks.delete(id=webhook_id)
except (errors.APIError, GeminiNextGenAPIClientError) as exc:
    print(f"Webhook {operation} failed for {webhook_id}: {exc}", file=sys.stderr)
    raise
