#!/usr/bin/env python
"""
Test script for Langfuse integration
Run this with: python test_langfuse.py
"""

import logging
from utils.langfuse_logger import get_langfuse_handler
from utils.llm import test_langfuse_integration

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Test the Langfuse integration
    logger.info("Testing Langfuse integration...")
    success, message = test_langfuse_integration()
    
    if success:
        logger.info(f"✅ Langfuse test successful: {message}")
    else:
        logger.error(f"❌ Langfuse test failed: {message}")
        
    # Also get the Langfuse handler directly and inspect it
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler:
        logger.info(f"Langfuse handler type: {type(langfuse_handler)}")
        logger.info(f"Available methods: {[method for method in dir(langfuse_handler) if not method.startswith('_')]}")
        
        # Try creating a trace and span
        try:
            trace = langfuse_handler.trace(name="test_direct_trace")
            logger.info(f"Created trace of type: {type(trace)}")
            logger.info(f"Trace methods: {[method for method in dir(trace) if not method.startswith('_')]}")
            
            # Try creating a span
            try:
                span = trace.span(name="test_span")
                logger.info(f"Created span of type: {type(span)}")
                logger.info(f"Span methods: {[method for method in dir(span) if not method.startswith('_')]}")
                
                # Try different observation methods
                logger.info("Testing different observation methods...")
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
                    logger.warning("No compatible observation method found on span")
                
                # Try end method if available
                if hasattr(span, "end"):
                    span.end()
                    logger.info("Successfully called span.end()")
                
            except Exception as e:
                logger.error(f"Error creating or using span: {e}")
            
            # Try end method if available
            if hasattr(trace, "end"):
                trace.end()
                logger.info("Successfully called trace.end()")
            
        except Exception as e:
            logger.error(f"Error creating or using trace: {e}")
    else:
        logger.error("Could not initialize Langfuse handler")

if __name__ == "__main__":
    main()
