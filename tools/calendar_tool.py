from utils.llm import llm_think
from datetime import datetime, timedelta
import logging
import pytz
import json

class CalendarTool:
    def extract_date_intent(self, message: str):
        """
        Use the LLM to extract date and time preferences from the message.
        This is more robust than regex patterns for handling natural language and multiple languages.
        """
        # Use CET timezone explicitly
        cet_timezone = pytz.timezone('Europe/Paris')
        now = datetime.now(cet_timezone)
        today = now.strftime("%A, %B %d, %Y")
        tomorrow = (now + timedelta(days=1)).strftime("%A, %B %d, %Y")
        
        # Calculate next Monday for "next week" reference
        days_until_next_monday = (7 - now.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7  # If today is Monday, go to next Monday
        next_monday = now + timedelta(days=days_until_next_monday)
        next_week_start = next_monday.strftime("%A, %B %d, %Y")
        
        # Calculate this Friday for "end of week" reference
        days_until_friday = (4 - now.weekday()) % 7
        this_friday = now + timedelta(days=days_until_friday)
        end_of_week = this_friday.strftime("%A, %B %d, %Y")
        
        # Current weekday name for reference
        current_weekday = now.strftime("%A")

        prompt = f"""
Today is {today} ({current_weekday}).
Tomorrow will be {tomorrow}.
Next week starts on {next_week_start}.
End of this week is {end_of_week}.

Analyze this customer message and extract any date/time preferences for scheduling a meeting:
"{message}"

Return a JSON object with the following fields:
1. "has_date_request": true if the message contains any date or time preferences, false otherwise
2. "date_intent_type": one of these values: "today", "tomorrow", "this_week", "end_of_week", "next_week", "specific_day", "specific_date", "weekend", "custom", or null if no date request
3. "date_description": a brief human-readable description of the requested time (e.g., "end of this week", "next Tuesday", etc.), or null if not specified
4. "reasoning": a brief explanation of why you determined this date intent

Be sure to understand contextual clues and natural language references to dates and times in ANY language.
For example, "end of this week" should be interpreted as Thursday or Friday of the current week.

Only return the JSON object without any other text.
"""

        logging.info(f"Date Intent Extraction Prompt: {prompt}")
        response, _ = llm_think(prompt)
        logging.info(f"Date Intent Extraction Response: {response}")
        
        try:
            result = json.loads(response)
            return result
        except Exception as e:
            logging.error(f"Error parsing date intent response: {e}")
            # Return a default object if parsing fails
            return {
                "has_date_request": False,
                "date_intent_type": None,
                "date_description": None,
                "reasoning": "Failed to parse LLM response"
            }
    
    def schedule(self, lead_message: str):
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
        
        # Extract date intent using LLM
        date_intent = self.extract_date_intent(lead_message)
        has_date_request = date_intent.get("has_date_request", False)
        date_intent_type = date_intent.get("date_intent_type")
        date_description = date_intent.get("date_description")
        reasoning = date_intent.get("reasoning", "")
        
        # Log the date intent extraction for debugging
        logging.info(f"Date intent extraction: {date_intent}")
        
        # Construct date guidance based on intent
        if has_date_request and date_intent_type:
            date_guidance = f"The customer specifically indicated a preference for {date_description}. " \
                           f"The intent type is \"{date_intent_type}\". Reasoning: {reasoning}. " \
                           f"Prioritize scheduling according to this preference."
        else:
            date_guidance = f"No specific date was requested. The meeting should ideally be scheduled for next week starting from {next_week_start} or later."

        prompt = f"""
Today is {today}.

A customer sent the following message:

\"\"\"{lead_message}\"\"\"

{date_guidance}
Consider normal business hours (9 AM - 5 PM CET) and avoid weekends unless specifically requested.

DO NOT INCLUDE "CET" or "CEST" in your datetime response as it will cause parsing errors.

Return a response in valid JSON format with the following fields:
1. "datetime": the suggested date and time in the format "Monday, April 28, 2025 at 10:00 AM" (without timezone indicator)
2. "mode": the mode of the meeting (online or in-person)
3. "subject": a relevant subject line for the meeting based on the message
4. "has_specific_date_request": {str(has_date_request).lower()}
5. "date_intent_type": "{date_intent_type if date_intent_type else ''}"

Only return the JSON object without any other text.
"""

        logging.info(f"LLM Calendar Prompt: {prompt}")
        response, tokens = llm_think(prompt)
        logging.info(f"LLM Calendar Response: {response}")
        return response
