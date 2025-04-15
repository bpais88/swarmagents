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
load_dotenv(dotenv_path=env_path)

# Get the API key
api_key = os.getenv("OPENAI_API_KEY")

# If that didn't work, try to parse the .env file directly
if not api_key and env_