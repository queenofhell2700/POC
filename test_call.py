import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Calling gemini-2.5-flash-lite with tiny prompt...")
resp = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents="Say the word 'hello' and nothing else.",
    config=types.GenerateContentConfig(response_mime_type="text/plain"),
)
print("Response:", resp.text)
