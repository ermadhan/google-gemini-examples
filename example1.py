from google import genai
import os

# Set GEMINI_API_KEY in the environment before running this script.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# Choose a supported Gemini model.
MODEL_ID = "gemini-3.5-flash-lite"

# Create a chat session, then send a message within that session.
chat = client.chats.create(model=MODEL_ID)
response = chat.send_message("Hello, how are you?")

print(response.text)

# Run a separate interaction and print the text from its final response step.
interaction = client.interactions.create(
    model=MODEL_ID,
    input="Please give me python code to sort a list."
)

# The response is an Interaction object containing a list of steps.
# Each step represents a part of the model's response.
# Let's look at what the steps contain:
print(f"Number of steps: {len(interaction.steps)}")
for j, step in enumerate(interaction.steps):
    print(f"  Step {j}: type={step.type}")

print(interaction.steps[-1].content[0].text)