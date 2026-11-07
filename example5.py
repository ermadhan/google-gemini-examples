#https://github.com/google-gemini/cookbook/blob/main/quickstarts/Webhooks.ipynb
import os
from google import genai
from google.genai import errors, types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Set the GEMINI_API_KEY environment variable before running this script.")

client = genai.Client(api_key=GEMINI_API_KEY)

WEBHOOK_ENDPOINT="https://gemini-webhook-receiver-670516618964.europe-west1.run.app/"

import requests

r = requests.get(WEBHOOK_ENDPOINT)
print(r.text)