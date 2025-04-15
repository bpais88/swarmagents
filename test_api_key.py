"""Test if the OpenAI API key is valid"""
import os
from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI

# Find the .env file
root_dir = Path(__file__).parent.absolute()
env_path = root_dir / '.env'

# Load environment variables
load_dotenv(dotenv_path=env_path)

# Get API key directly
with open(env_path, 'r') as file:
    for line in file:
        if line.startswith('OPENAI_API_KEY='):
            api_key = line.strip().split('=', 1)[1]
            api_key = api_key.strip('"\'')
            break
    else:
        api_key = None

# Show the API key (first few characters)
if api_key:
    print(f"API key found (starts with: {api_key[:10]}...)")
else:
    print("No API key found in .env file")

# Try a direct API call using the extracted key
try:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Using a simpler model for testing
        messages=[
            {"role": "user", "content": "Say hello"}
        ]
    )
    print("API call successful!")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"API call failed: {str(e)}") 