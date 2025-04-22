from utils.llm import llm_think
from datetime import datetime, timedelta
import logging
import pytz
import re

class CalendarTool:
    def detect_date_intent(self, message):
        """
        Detect if the message contains a specific date request like 'tomorrow', 'today', etc.
        Returns a tuple (has_date_intent, intent_type, date_reference)
        """
        message = message.lower()
        
        # Check for common date references
        tomorrow_patterns = [r'\btomorrow\b', r'\bnext day\b']
        today_patterns = [r'\btoday\b', r'\bthis day\b']
        this_week_patterns = [r'\bthis week\b', r'\bcurrent week\b']
        specific_day_patterns = [
            r'\bmonday\b', r'\btuesday\b', r'\bwednesday\b', 
            r'\bthursday\b', r'\bfriday\b', r'\bsaturday\b', r'\bsunday\b'
        ]
        
        # Check for tomorrow references
        if any(re.search(pattern, message) for pattern in tomorrow_patterns):
            return (True, "tomorrow", "tomorrow")
            
        # Check for today references
        if any(re.search(pattern, message) for pattern in today_patterns):
            return (True, "today", "today")
            
        # Check for this week references
        if any(re.search(pattern, message) for pattern in this_week_patterns):
            return (True, "this_week", "this week")
        
        # Check for specific day references
        for day_pattern in specific_day_patterns:
            if re.search(day_pattern, message):
                day = re.search(day_pattern, message).group(0)
                return (True, "specific_day", day)
                
        # No specific date reference found
        return (False, None, None)
    
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
        
        # Also provide a date 10 days out to give more context
        future_date = now + timedelta(days=10)
        future_date_str = future_date.strftime("%A, %B %d, %Y")
        
        # Detect if the message has a specific date intent
        has_date_intent, intent_type, date_reference = self.detect_date_intent(lead_message)
        
        # Construct date guidance based on intent
        if has_date_intent:
            if intent_type == "tomorrow":
                date_guidance = f"The customer specifically asked about meeting tomorrow ({tomorrow}). If possible, prioritize scheduling for tomorrow."
            elif intent_type == "today":
                date_guidance = f"The customer specifically asked about meeting today ({today}). If possible, prioritize scheduling for today."
            elif intent_type == "this_week":
                date_guidance = f"The customer specifically asked about meeting this week. Prioritize dates within this week if available."
            elif intent_type == "specific_day":
                date_guidance = f"The customer specifically asked about meeting on {date_reference}. Try to find a suitable time on that day."
        else:
            date_guidance = f"No specific date was requested. The meeting should ideally be scheduled for next week starting from {next_week_start} or later."

        prompt = f"""
Today is {today}.

A customer sent the following message:

\"\"\"{lead_message}\"\"\"

{date_guidance}
Consider normal business hours (9 AM - 5 PM CET) and avoid weekends.

DO NOT INCLUDE "CET" or "CEST" in your datetime response as it will cause parsing errors.

Return a response in valid JSON format with the following fields:
1. "datetime": the suggested date and time in the format "Monday, April 28, 2025 at 10:00 AM" (without timezone indicator)
2. "mode": the mode of the meeting (online or in-person)
3. "subject": a relevant subject line for the meeting based on the message
4. "has_specific_date_request": true if the customer requested a specific date, false otherwise

Only return the JSON object without any other text.
"""

        logging.info(f"LLM Calendar Prompt: {prompt}")
        response, tokens = llm_think(prompt)
        logging.info(f"LLM Calendar Response: {response}")
        return response
