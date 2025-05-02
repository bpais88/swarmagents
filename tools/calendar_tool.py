from utils.llm import llm_think
from datetime import datetime, timedelta
import logging
import pytz
import json
from utils.langfuse_logger import get_langfuse_handler

# Get Langfuse handler
langfuse_handler = get_langfuse_handler()

def add_observation_safely(span, name, value=None, metadata=None):
    """
    Safely add an observation to a Langfuse span, handling different API versions.
    Falls back gracefully if methods don't exist.
    """
    if not span:
        return
        
    try:
        # Try observation method first (pre-2.0)
        if hasattr(span, "observation"):
            if value is not None:
                span.observation(name=name, value=value, metadata=metadata or {})
            else:
                span.observation(name=name, metadata=metadata or {})
        # Try add_observation next (some versions)
        elif hasattr(span, "add_observation"):
            if value is not None:
                span.add_observation(name=name, value=value, metadata=metadata or {})
            else:
                span.add_observation(name=name, metadata=metadata or {})
        # Fall back to event (Langfuse 2.0)
        elif hasattr(span, "event"):
            event_metadata = metadata or {}
            if value is not None:
                event_metadata["value"] = value
            span.event(name=name, metadata=event_metadata)
        else:
            logging.warning("Unable to log observation to Langfuse: no compatible method found on span")
    except Exception as e:
        logging.warning(f"Failed to log observation to Langfuse: {str(e)}")

class CalendarTool:
    def extract_date_intent(self, message: str):
        """
        Use the LLM to extract date and time preferences from the message.
        This is more robust than regex patterns for handling natural language and multiple languages.
        """
        # Create a Langfuse trace for date extraction
        extract_trace = None
        date_span = None
        
        if langfuse_handler:
            try:
                extract_trace = langfuse_handler.trace(
                    name="extract_date_intent",
                    metadata={
                        "message_length": len(message),
                        "timestamp": datetime.now().isoformat()
                    }
                )
            except Exception as e:
                logging.warning(f"Failed to create Langfuse trace: {str(e)}")
            
        # Use CET timezone explicitly
        cet_timezone = pytz.timezone('Europe/Paris')
        now = datetime.now(cet_timezone)
        today = now.strftime("%A, %B %d, %Y")
        tomorrow = (now + timedelta(days=1)).strftime("%A, %B %d, %Y")
        
        # Calculate next Monday for "next week" reference
        days_until_next_monday = (7 - now.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7  # If today is Monday, go to next Monday
        next_week_start = (now + timedelta(days=days_until_next_monday)).strftime("%A, %B %d, %Y")
        
        # Analyze the message for date/time preferences
        date_analysis_prompt = f"""
Analyze this message for date and time preferences:

"{message}"

Today is {today}.
Tomorrow is {tomorrow}.
Next week starts on {next_week_start}.

Return a JSON object with:
1. has_date_request: true/false - if the message contains a specific date/time request
2. date_intent_type: one of ["specific_date", "relative_date", "next_week", "none"]
3. parsed_date: the date mentioned (if any) in natural language
4. confidence: 0-1 score of how confident you are in the date extraction

Only return the JSON object without any other text.
"""
        if extract_trace:
            try:
                date_span = extract_trace.span(
                    name="date_analysis",
                    metadata={"prompt_length": len(date_analysis_prompt)}
                )
            except Exception as e:
                logging.warning(f"Failed to create date analysis span: {str(e)}")
            
        analysis_response, tokens = llm_think(date_analysis_prompt)
            
        try:
            analysis = json.loads(analysis_response)
            has_date_request = analysis.get("has_date_request", False)
            date_intent_type = analysis.get("date_intent_type", "none")
            confidence = analysis.get("confidence", 0)
            
            if date_span:
                add_observation_safely(
                    date_span,
                    name="date_analysis_result",
                    value=confidence,
                    metadata=analysis
                )
                
            return has_date_request, date_intent_type
            
        except json.JSONDecodeError as e:
            if date_span:
                add_observation_safely(
                    date_span,
                    name="date_analysis_error",
                    value=0,
                    metadata={"error": str(e), "raw_response": analysis_response}
                )
            logging.error(f"Failed to parse date analysis response: {e}")
            return False, "none"

    def schedule(self, lead_message: str):
        # Create a Langfuse trace for scheduling
        schedule_trace = None
        schedule_span = None
        
        if langfuse_handler:
            try:
                schedule_trace = langfuse_handler.trace(
                    name="schedule_meeting",
                    metadata={
                        "message_length": len(lead_message),
                        "timestamp": datetime.now().isoformat()
                    }
                )
            except Exception as e:
                logging.warning(f"Failed to create schedule trace: {str(e)}")
            
        # Use CET timezone explicitly
        cet_timezone = pytz.timezone('Europe/Paris')
        now = datetime.now(cet_timezone)
        today = now.strftime("%A, %B %d, %Y")
        tomorrow = (now + timedelta(days=1)).strftime("%A, %B %d, %Y")
        
        # Calculate next Monday for "next week" scheduling
        days_until_next_monday = (7 - now.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7  # If today is Monday, go to next Monday
        next_monday = now + timedelta(days=days_until_next_monday)
        next_week_start = next_monday.strftime("%A, %B %d, %Y")
        
        # Extract date intent first
        has_date_request, date_intent_type = self.extract_date_intent(lead_message)
        
        # Prepare scheduling prompt based on date intent
        if has_date_request:
            date_guidance = f"The customer has expressed a specific date/time preference ({date_intent_type}). " + \
                           f"Prioritize scheduling according to this preference."
        else:
            date_guidance = f"No specific date was requested. The meeting should ideally be scheduled for next week starting from {next_week_start} or later."

        prompt = f"""
Today is {today}.

A customer sent the following message:

"{lead_message}"

{date_guidance}
Consider normal business hours (9 AM - 5 PM CET) and avoid weekends unless specifically requested.

Return a JSON object with:
1. "datetime": the suggested date and time in the format "Monday, April 28, 2025 at 10:00 AM" (without timezone indicator)
2. "mode": the mode of the meeting (online or in-person)
3. "subject": a relevant subject line for the meeting based on the message
4. "has_specific_date_request": {str(has_date_request).lower()}
5. "date_intent_type": "{date_intent_type if date_intent_type else ''}"

Only return the JSON object without any other text.
"""
        if schedule_trace:
            try:
                schedule_span = schedule_trace.span(
                    name="schedule_generation",
                    metadata={"prompt_length": len(prompt)}
                )
            except Exception as e:
                logging.warning(f"Failed to create schedule generation span: {str(e)}")
            
        logging.info(f"LLM Calendar Prompt: {prompt}")
        response, tokens = llm_think(prompt)
        logging.info(f"LLM Calendar Response: {response}")
        
        if schedule_span:
            try:
                schedule_data = json.loads(response)
                add_observation_safely(
                    schedule_span,
                    name="schedule_result",
                    value=1 if schedule_data.get("datetime") else 0,
                    metadata=schedule_data
                )
            except json.JSONDecodeError as e:
                add_observation_safely(
                    schedule_span,
                    name="schedule_error",
                    value=0,
                    metadata={"error": str(e), "raw_response": response}
                )
            
        return response
