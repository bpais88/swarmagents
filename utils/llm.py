from openai import OpenAI, APIConnectionError, RateLimitError, APIError
import os
import logging
from dotenv import load_dotenv
from pathlib import Path
import re
from utils.langfuse_logger import get_langfuse_handler

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

# Initialize Langfuse handler
langfuse_handler = get_langfuse_handler()

def llm_think(prompt):
    try:
        # Start a new span for this LLM call if we're inside a trace
        span = None
        if langfuse_handler:
            span = langfuse_handler.span(
                name="llm_call",
                metadata={
                    "model": "gpt-4",
                    "prompt_length": len(prompt),
                    "temperature": 0.3
                }
            )

        response = client.chat.completions.create(
            model="gpt-4",  # or "gpt-3.5-turbo" for cheaper tests
            messages=[
                {"role": "system", "content": "You're a helpful assistant focused on providing clear, accurate, and well-reasoned responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens

        # Log the completion in Langfuse - safely calling methods that might not exist
        if span:
            try:
                # Try observation method first (pre-2.0)
                if hasattr(span, "observation"):
                    span.observation(
                        name="llm_response",
                        value=tokens_used,
                        metadata={
                            "completion_length": len(content),
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens
                        }
                    )
                # Try add_observation next (some versions)
                elif hasattr(span, "add_observation"):
                    span.add_observation(
                        name="llm_response",
                        value=tokens_used,
                        metadata={
                            "completion_length": len(content),
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens
                        }
                    )
                # Fall back to event (Langfuse 2.0)
                elif hasattr(span, "event"):
                    span.event(
                        name="llm_response",
                        metadata={
                            "completion_length": len(content),
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": tokens_used
                        }
                    )
                # If none of these methods exist, log the issue
                else:
                    logger.warning("Unable to log observation to Langfuse: no compatible method found on span")
            except Exception as e:
                logger.warning(f"Failed to log observation to Langfuse: {str(e)}")

        return content, tokens_used

    except APIConnectionError as e:
        logger.error(f"Could not connect to OpenAI: {str(e)}")
        if span:
            log_error_safely(span, "connection", str(e))
        return "Connection error", 0

    except RateLimitError as e:
        logger.error(f"Rate limit exceeded: {str(e)}")
        if span:
            log_error_safely(span, "rate_limit", str(e))
        return "Rate limit exceeded", 0

    except APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        if span:
            log_error_safely(span, "api", str(e))
        return "API error", 0

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        if span:
            log_error_safely(span, "unexpected", str(e))
        return "Unexpected error", 0

def log_error_safely(span, error_type, error_message):
    """Safely log an error to Langfuse span, handling different API versions"""
    try:
        # Try observation method first (pre-2.0)
        if hasattr(span, "observation"):
            span.observation(
                name="llm_error",
                value=0,
                metadata={"error_type": error_type, "error": error_message}
            )
        # Try add_observation next (some versions)
        elif hasattr(span, "add_observation"):
            span.add_observation(
                name="llm_error",
                value=0,
                metadata={"error_type": error_type, "error": error_message}
            )
        # Fall back to event (Langfuse 2.0)
        elif hasattr(span, "event"):
            span.event(
                name="llm_error",
                metadata={"error_type": error_type, "error": error_message}
            )
        # If none of these methods exist, log the issue
        else:
            logger.warning("Unable to log error to Langfuse: no compatible method found on span")
    except Exception as e:
        logger.warning(f"Failed to log error to Langfuse: {str(e)}")

def test_langfuse_integration():
    """
    Test the Langfuse integration to ensure it's working properly.
    Returns a tuple of (success, message) where success is a boolean and message describes the test result.
    """
    try:
        if not langfuse_handler:
            return False, "Langfuse handler not initialized. Check your API credentials."
        
        # Create a test trace
        trace = langfuse_handler.trace(name="test_trace")
        
        # Create a test span
        span = trace.span(name="test_span", metadata={"test": True})
        
        # Try to log an event
        try:
            if hasattr(span, "event"):
                span.event(name="test_event", metadata={"test": True})
                logger.info("Successfully used event() method")
            elif hasattr(span, "observation"):
                span.observation(name="test_observation", value=1, metadata={"test": True})
                logger.info("Successfully used observation() method")
            elif hasattr(span, "add_observation"):
                span.add_observation(name="test_observation", value=1, metadata={"test": True})
                logger.info("Successfully used add_observation() method")
            else:
                return False, "No compatible observation method found on span"
        except Exception as e:
            return False, f"Error when trying to record observation: {str(e)}"
            
        return True, "Langfuse integration test passed successfully!"
    except Exception as e:
        return False, f"Langfuse test failed: {str(e)}"
