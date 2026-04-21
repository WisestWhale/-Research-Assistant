import os
from dotenv import load_dotenv
import anthropic

# Load .env file into environment variables
# This must run before anything tries to read the key
load_dotenv()

# Grab the key from environment — never hardcode it
api_key = os.getenv("ANTHROPIC_API_KEY")

# Fail loudly if key is missing — better than a confusing API error later
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found. Did you create your .env file?")

# Create the client — it reads the key automatically from environment
# You don't need to pass api_key= explicitly, but being explicit is fine too
client = anthropic.Anthropic()

# Make the API call
response = client.messages.create(
    model="claude-haiku-4-5-20251001",   # cheapest/fastest model — good for learning
    max_tokens=12,                       # hard cap on response length
    system="You are a helpful assistant. Be concise.",  # system prompt
    messages=[
        {"role": "user", "content": "What is a REST API? Explain in 2 sentences."}
    ]
)

# response.content is a list of blocks — text is always in block[0].text
print(response.content[0].text)

# Bonus: print token usage so you understand cost/limits
print(f"\n--- Usage ---")
print(f"Input tokens:  {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")