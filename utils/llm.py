from openai import OpenAI, APIConnectionError, RateLimitError, APIError
import os
import logging
from dotenv import load_dotenv
from pathlib import Path
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Find the root directory and load .env file
root_dir = Path(__file__).parent.parent.absolute()
env_path = root_dir / '.env'

# Clear any existing OPENAI_API_KEY from the environment
if "OPENAI_API_KEY" in os.environ:
    logger.info("Clearing existing OPENAI_API_KEY from environment")
    del os.environ["OPENAI_API_KEY"]

# First try loading with dotenv
load_dotenv()

# Get the API key
api_key = os.getenv("OPENAI_API_KEY")

# If that didn't work, try to parse the .env file directly
if not api_key and env_path.exists():
    logger.info(f"Trying to parse .env file directly from: {env_path}")
    try:
        with open(env_path, 'r') as file:
            for line in file:
                if line.startswith('OPENAI_API_KEY='):
                    # Extract everything after the equals sign
                    api_key = line.strip().split('=', 1)[1]
                    # Remove any quotes if present
                    api_key = api_key.strip('"\'')
                    # Set it in environment for other parts of the application
                    os.environ["OPENAI_API_KEY"] = api_key
                    logger.info("Successfully parsed API key from .env file")
                    break
            else:
                logger.error("Could not find OPENAI_API_KEY in .env file")
    except Exception as e:
        logger.error(f"Error reading .env file: {str(e)}")

if not api_key:
    logger.error(f"OPENAI_API_KEY not found. Looking for .env in: {env_path}")
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Log the first few characters of the API key for debugging
if api_key:
    logger.info(f"API key found (starts with: {api_key[:10]}...)")

client = OpenAI(api_key=api_key)

def llm_think(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # or "gpt-3.5-turbo" for cheaper tests
            messages=[
                {"role": "system", "content": "You're a helpful assistant focused on providing clear, accurate, and well-reasoned responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            timeout=30,  # Add timeout to prevent hanging
        )
        content = response.choices[0].message.content.strip()
        tokens_used = response.usage.total_tokens
        return content, tokens_used
    except APIConnectionError as e:
        logger.error(f"Could not connect to OpenAI: {str(e)}")
        return "Connection error", 0
    except RateLimitError as e:
        logger.error(f"Rate limit exceeded: {str(e)}")
        return "Rate limit exceeded", 0
    except APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return "API error", 0
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return "Unexpected error", 0
