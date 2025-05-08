"""
Calendar Agent: Handles meeting scheduling, availability checks.
"""
import json
import logging
import pytz
from datetime import datetime, timedelta

# Assuming tools are correctly initialized and passed or globally available
# This requires tools/calendar_tool.py and tools/google_calendar_tool.py
# and potentially memory/supabase_memory.py depending on how state is managed.
from tools.calendar_tool import CalendarTool 
from tools.google_calendar_tool import GoogleCalendarOAuthTool
from memory.supabase_memory import memory # If needed for lead info

calendar_tool = CalendarTool()

def schedule_meeting(lead_message: str, access_token: str) -> dict:
    """Attempts to schedule a meeting based on lead message and access token."""
    thoughts = []
    tools_used = []
    event_details = {}
    error_message = None
    tokens = {"input": 0, "output": 0, "total": 0} # Placeholder for potential LLM calls within tools
    meeting_link = None
    meeting_time = None
    meeting_type = "professional" # Default

    if not access_token:
        return {
            "thought": "[Calendar Agent] Cannot proceed without Google Calendar access token.",
            "error": "Missing Google access token",
            "tokens": tokens,
            "tools_used": tools_used
        }

    try:
        # Initialize the Google Calendar API tool with the token
        calendar_api = GoogleCalendarOAuthTool(access_token=access_token)
        tools_used.append("GoogleCalendarTool")

        # Use the existing calendar_tool's schedule method (which likely calls LLM internally)
        raw_json = calendar_tool.schedule(lead_message) 
        tools_used.append("CalendarTool.schedule")
        # TODO: Incorporate token counting if calendar_tool.schedule provides it.

        try:
            data = json.loads(raw_json)
            thoughts.append(f"[Calendar Agent] Parsed scheduling suggestion: {data}")

            # Use CET timezone for parsing - consider making this configurable or using user's timezone
            cet_timezone = pytz.timezone('Europe/Paris')
            datetime_str = data.get("datetime")
            if not datetime_str:
                raise ValueError("No datetime found in suggestion")

            if " CET" in datetime_str or " CEST" in datetime_str:
                datetime_str = datetime_str.replace(" CET", "").replace(" CEST", "")

            try:
                preferred_time_dt = datetime.strptime(datetime_str, "%A, %B %d, %Y at %I:%M %p")
            except ValueError:
                preferred_time_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            
            preferred_time = cet_timezone.localize(preferred_time_dt)
            meeting_time = preferred_time.strftime("%A, %B %d, %Y at %I:%M %p %Z") 
            thoughts.append(f"[Calendar Agent] Parsed preferred time: {meeting_time}")

            duration = int(data.get("duration", 30))
            title = data.get("title", "Meeting")
            description = data.get("description", f"Meeting requested via: {lead_message}")
            location = data.get("location", "")
            
            # Check Availability (This logic was added in orchestrator/graph.py previously)
            # For consistency, it should ideally live here or be called from here.
            # Re-implementing the check logic within the agent:
            thoughts.append("[Calendar Agent] Checking availability...")
            tools_used.append("GoogleCalendarTool.get_busy_slots")
            busy_slots = calendar_api.get_busy_slots(preferred_time.date())
            
            tools_used.append("GoogleCalendarTool.is_slot_free")
            is_free = calendar_api.is_slot_free(
                start=preferred_time, 
                end=preferred_time + timedelta(minutes=duration),
                busy_slots=busy_slots
            )

            if is_free:
                thoughts.append(f"[Calendar Agent] Slot {meeting_time} is available. Creating event.")
                meeting_link = calendar_api.create_event(
                    summary=title,
                    description=description,
                    start_time=preferred_time,
                    duration_minutes=duration,
                    location=location
                )
                tools_used.append("GoogleCalendarTool.create_event")
                thoughts.append(f"[Calendar Agent] Successfully created calendar event: {meeting_link}")
            else:
                error_message = f"Time slot conflict detected for {meeting_time}"
                thoughts.append(f"[Calendar Agent] {error_message}")

        except (json.JSONDecodeError, ValueError, KeyError) as parse_error:
            logging.error(f"Calendar Agent - Error parsing or processing schedule data: {parse_error}")
            error_message = f"Failed to parse scheduling suggestion: {parse_error}"
            thoughts.append(f"[Calendar Agent] {error_message} (Raw response: {raw_json[:100]}...)")

    except Exception as e:
        logging.error(f"Calendar Agent - Unexpected error: {e}", exc_info=True)
        error_message = f"Unexpected calendar processing error: {str(e)}"
        thoughts.append(f"[Calendar Agent] {error_message}")

    # Construct return dictionary
    result = {
        "thought": "\n".join(thoughts),
        "tokens": tokens,
        "tools_used": tools_used
    }
    # Only include meeting details if successfully scheduled AND no error occurred
    if meeting_link and not error_message:
        result["calendar_link"] = meeting_link
        result["meeting_time"] = meeting_time 
        result["meeting_type"] = meeting_type 
    if error_message:
        result["error"] = error_message
        
    return result 