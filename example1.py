from google import genai
import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

#gemini-3.5-flash-lite
#gemini-3.6-flash
#gemini-3.7-flash
MODEL_ID = "gemini-3.5-flash-lite"

# 1. Initialize a stateful chat session (note the plural 'chats')
chat = client.chats.create(model=MODEL_ID)

# 2. Send the user message to the session
response = chat.send_message("Hello, how are you?")

# 3. Print the text content of the reply
print(response.text)

interaction = client.interactions.create(
    model=MODEL_ID,
    input="Please give me python code to sort a list."
)

print(interaction.steps[-1].content[0].text)