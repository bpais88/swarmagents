import os
from dotenv import load_dotenv
from langfuse import Langfuse
import logging

# Load environment variables
load_dotenv()

def get_langfuse_handler():
    """
    Creates and returns a Langfuse client using credentials from environment variables.
    Returns None if the required credentials are not available.
    """
    try:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        
        if not public_key or not secret_key:
            logging.warning("Langfuse credentials not found in environment variables. Telemetry disabled.")
            return None
            
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
    except Exception as e:
        logging.error(f"Failed to initialize Langfuse: {e}")
        return None
