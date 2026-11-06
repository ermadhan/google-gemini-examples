from google import genai
import os

# Set GEMINI_API_KEY in the environment before running this script.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# Choose a supported Gemini model.
MODEL_ID = "gemini-3.5-flash-lite"

# Ask Gemini a question and inspect the response steps before printing the full text.
interaction = client.interactions.create(
    model=MODEL_ID,
    input="Explain how AI works in a few words"
)

# The response is an Interaction object containing a list of steps.
# Each step represents a part of the model's response.
# Let's look at what the steps contain:
print(f"Number of steps: {len(interaction.steps)}")
for j, step in enumerate(interaction.steps):
    print(f"  Step {j}: type={step.type}")

print(interaction.output_text)

# A system instruction controls the style and audience of the response.
print("----------------------------------------------------------------")
system_instruction = "You are a pirate and are explaining things to 5 years old kids."

interaction = client.interactions.create(
    model=MODEL_ID,
    input="Explain how AI works",
    system_instruction=system_instruction,
)

print("You are a pirate and are explaining things to 5 years old kids.")
print("----------------------------------------------------------------")
print(interaction.steps[-1].content[0].text)

print("----------------------------------------------------------------")
system_instruction = "You are a pirate and are explaining things to 72 years old."

interaction = client.interactions.create(
    model=MODEL_ID,
    input="Explain how AI works",
    system_instruction=system_instruction,
)
print("You are a pirate and are explaining things to 72 years old.")
print("----------------------------------------------------------------")
print(interaction.steps[-1].content[0].text)

print("----------------------------------------------------------------")
print("What's the highest mountain in Africa?")
# Estimate the token count for a prompt without generating a response.
response = client.models.count_tokens(
    model=MODEL_ID,
    contents="What's the highest mountain in Africa?",
)

print(f"*This prompt was worth {response.total_tokens} tokens.")
print("----------------------------------------------------------------")

print("Tell me how the internet works, but pretend I'm a puppy who understands only dog-related analogies.")
print("----------------------------------------------------------------")
# Limit the maximum number of tokens Gemini can generate for this response.
interaction = client.interactions.create(
    model=MODEL_ID,
    input="Tell me how the internet works, but pretend I'm a puppy who understands only dog-related analogies.",
    generation_config={
        "max_output_tokens": 1000,  # In Gemini 3, this includes both thought and response tokens
    },
)

print(interaction.output_text)

print("----------------------------------------------------------------")
print("A man moves his car to a hotel and tells the owner he's bankrupt. Why?")
print("----------------------------------------------------------------")
# Set the model's reasoning effort for this request.
thinking_level = "high"

interaction = client.interactions.create(
    model=MODEL_ID,
    input="A man moves his car to a hotel and tells the owner he's bankrupt. Why?",
    generation_config={"thinking_level": thinking_level},
)

# Print thought-step metadata when present, along with the model's answer.
for step in interaction.steps:
    if step.type == "thought":
        print("💭 Thought:", getattr(step, "text", "")[:200] if hasattr(step, "text") else "(thinking...)")
    elif step.type == "model_output" and step.content:
        print(step.content[0].text)
print("----------------------------------------------------------------")

print("What was the weather during the last soccer world cup final?")

print("----------------------------------------------------------------")
# Request another answer and check whether the response includes a thought signature.
interaction_with_thinking = client.interactions.create(
    model=MODEL_ID,
    input="What was the weather during the last soccer world cup final?",
)

# Print the thought signature from the response
for step in interaction_with_thinking.steps:
    if step.type == "thought" and hasattr(step, 'signature') and step.signature:
        # Only display the first 100 characters to keep notebook size manageable
        print(f"Thought signature: {step.signature[:100]}...")
        break 
else:
    print("No thought signature found in this response.")
print("----------------------------------------------------------------")

# Upload a local image, then include its file URI in a multimodal prompt.
image_filename = "generated_elephants_giraffes_zebras_sunset.jpg"
print("----------------------------------------------------------------")
print("What do you see in this image? Describe it briefly.")
print("----------------------------------------------------------------")
# Upload the image to the Gemini File API
file_upload = client.files.upload(file=image_filename)
interaction = client.interactions.create(
    model=MODEL_ID,
    input=[
        {
            "type": "image",
            "uri": file_upload.uri,
        },
        {"type": "text", "text": "What do you see in this image? Describe it briefly."},
    ],
)
print(interaction.output_text)
print("----------------------------------------------------------------")
    