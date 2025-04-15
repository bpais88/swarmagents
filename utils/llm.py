
import openai
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def llm_think(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You're a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )
    content = response.choices[0].message.content.strip()
    tokens_used = response.usage.total_tokens
    return content, tokens_used
