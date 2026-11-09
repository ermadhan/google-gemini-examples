# Generate an image and save the returned base64-encoded bytes as a PNG.
import base64
from pathlib import Path
import os
from google import genai
from google.genai import types

# Set GEMINI_API_KEY in the environment before running this script.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Set the GEMINI_API_KEY environment variable before running this script.")

# Image generation can take longer than a text request; the timeout is in milliseconds.
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=180_000),
)
MODEL_ID = "gemini-nano-banana-2.1"

print("Sending image generation request; this may take a little while...", flush=True)
interaction = client.interactions.create(
    model=MODEL_ID,
    input="Generate an image of a cat wearing a top hat in a library.",
)
# The Interactions API exposes generated image data through output_image.
if interaction.output_image and interaction.output_image.data:
    image_path = Path("generated_image.png")
    image_path.write_bytes(base64.b64decode(interaction.output_image.data))
    print(f"Generated image saved to {image_path.resolve()}")
else:
    raise RuntimeError(
        f"The model returned no image. Response text: {interaction.output_text or '(none)'}"
    )