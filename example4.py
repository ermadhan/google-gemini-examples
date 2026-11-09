# Continue an Interactions API conversation using the previous interaction ID.
import os
from google import genai

# Set GEMINI_API_KEY in the environment before running this script.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Set the GEMINI_API_KEY environment variable before running this script.")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-3.5-flash-lite"

print("Why is the same side of the Moon always visible from Earth? Keep it short.")
print("----------------------------------------------------------------")
# Ask an initial question and print the model's answer.
turn_1 = client.interactions.create(
    model=MODEL_ID,
    input="Why is the same side of the Moon always visible from Earth? Keep it short.",
)

print(turn_1.output_text)
print("----------------------------------------------------------------")
print("Interesting! Has any human or spacecraft actually seen the far side?")
print("----------------------------------------------------------------")
# Continue the conversation by referencing the first interaction's ID.
turn_2 = client.interactions.create(
    model=MODEL_ID,
    input="Interesting! Has any human or spacecraft actually seen the far side?",
    previous_interaction_id=turn_1.id,
)

print(turn_2.output_text)
print("----------------------------------------------------------------")