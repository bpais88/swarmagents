from langgraph.graph import StateGraph, END
from memory.supabase_memory import memory
from tools.email_tool import EmailTool
from tools.calendar_tool import CalendarTool
from tools.google_calendar_tool import GoogleCalendarOAuthTool
from utils.llm import llm_think
from typing import TypedDict
import json
from datetime import datetime, timedelta, date, time
import pytz
import os
import logging

# Define the state structure
class GraphState(TypedDict):
    lead_message: str
    lead_rule: str
    calendar_done: bool
    reply_done: bool

email_tool = EmailTool()
calendar_tool = CalendarTool()


def run_graph(email_body: str, lead_rule: str, access_token: str):
    report = {"thoughts": [], "tools_used": [], "tokens": 0, "busy_slots": [], "all_checked_dates": {}, "event_details": {}}
    calendar_api = GoogleCalendarOAuthTool(access_token=access_token)

    def coordinator_node(state):
        email = {
            "from": "lead@example.com",
            "subject": email_body
        }
        report["tools_used"].append("EmailTool.read_email")

        prompt = f"""
Use the following rule to decide if this is a qualified lead:
{state['lead_rule']}

Here is the message from the lead:
{state['lead_message']}
"""
        thought, tokens = llm_think(prompt)
        report["thoughts"].append(f"[Inbox Agent] {thought}")
        report["tokens"] += tokens
        memory.set("lead", email)
        return {
            "lead_message": email["subject"],
            "lead_rule": state["lead_rule"]
        }

    def calendar_node(state):
        lead = memory.get("lead")
        lead_msg = state["lead_message"]

        raw_json = calendar_tool.schedule(lead_msg)
        try:
            data = json.loads(raw_json)
            # Use CET timezone for parsing the preferred time - strip timezone info from string first 
            cet_timezone = pytz.timezone('Europe/Paris')
            
            # Remove potential CET/CEST timezone suffix from datetime string to prevent parsing errors
            datetime_str = data["datetime"]
            if " CET" in datetime_str or " CEST" in datetime_str:
                datetime_str = datetime_str.replace(" CET", "").replace(" CEST", "")
                
            preferred_time = datetime.strptime(datetime_str, "%A, %B %d, %Y at %I:%M %p")
            preferred_time = cet_timezone.localize(preferred_time)
            mode = data.get("mode", "online")
            subject = data.get("subject", "AI project discussion")
            has_specific_date_request = data.get("has_specific_date_request", False)
            
            # Get the date intent type from the LLM
            date_intent_type = data.get("date_intent_type", "")
        except Exception as e:
            report["thoughts"].append(f"[Calendar Agent] Failed to parse meeting data: {e}")
            return {"calendar_done": False}

        # Get current time with CET timezone awareness
        now = datetime.now(pytz.timezone('Europe/Paris'))
        
        # If there's a specific date request, we should respect it
        if has_specific_date_request:
            report["thoughts"].append(f"[Calendar Agent] Customer has a specific date request: {date_intent_type}")
            
            # Determine start date based on intent type
            if date_intent_type == "today":
                start_date = now.date()
                report["thoughts"].append(f"[Calendar Agent] 'Today' requested. Checking from {start_date.strftime('%A, %B %d, %Y')}")
            
            elif date_intent_type == "tomorrow":
                start_date = now.date() + timedelta(days=1)
                report["thoughts"].append(f"[Calendar Agent] 'Tomorrow' requested. Checking from {start_date.strftime('%A, %B %d, %Y')}")
            
            elif date_intent_type == "this_week":
                # Start from today or tomorrow if today is almost over
                if now.hour >= 17:  # After 5pm, start from tomorrow
                    start_date = now.date() + timedelta(days=1)
                else:
                    start_date = now.date()
                report["thoughts"].append(f"[Calendar Agent] 'This week' requested. Checking from {start_date.strftime('%A, %B %d, %Y')}")
            
            elif date_intent_type == "end_of_week":
                # Calculate Thursday or Friday of this week
                today_weekday = now.weekday()
                if today_weekday <= 3:  # Mon-Wed
                    # Check if Thursday has full-day events
                    thursday_date = now.date() + timedelta(days=3 - today_weekday)
                    thursday_events = calendar_api.get_events(thursday_date)
                    thursday_has_full_day = any(event["is_full_day"] for event in thursday_events)
                    
                    # Check if Friday has full-day events
                    friday_date = now.date() + timedelta(days=4 - today_weekday)
                    friday_events = calendar_api.get_events(friday_date)
                    friday_has_full_day = any(event["is_full_day"] for event in friday_events)
                    
                    if thursday_has_full_day and friday_has_full_day:
                        # Both Thursday and Friday have full-day events, start from next Monday
                        days_until_next_monday = (7 - today_weekday) % 7
                        start_date = now.date() + timedelta(days=days_until_next_monday)
                        report["thoughts"].append(f"[Calendar Agent] Both Thursday and Friday have full-day events, suggesting next week instead: {start_date.strftime('%A, %B %d, %Y')}")
                    elif thursday_has_full_day:
                        # Thursday has full-day events, start from Friday
                        start_date = friday_date
                        report["thoughts"].append(f"[Calendar Agent] Thursday has full-day events, checking from Friday: {start_date.strftime('%A, %B %d, %Y')}")
                    else:
                        # Start from Thursday
                        start_date = thursday_date
                        report["thoughts"].append(f"[Calendar Agent] Checking from Thursday for 'end of week': {start_date.strftime('%A, %B %d, %Y')}")
                elif today_weekday == 4:  # Thursday
                    # Check if Thursday (today) has full-day events
                    thursday_events = calendar_api.get_events(now.date())
                    thursday_has_full_day = any(event["is_full_day"] for event in thursday_events)
                    
                    # Check if Friday has full-day events
                    friday_date = now.date() + timedelta(days=1)
                    friday_events = calendar_api.get_events(friday_date)
                    friday_has_full_day = any(event["is_full_day"] for event in friday_events)
                    
                    if thursday_has_full_day and friday_has_full_day:
                        # Both Thursday and Friday have full-day events, start from next Monday
                        days_until_next_monday = 4  # Monday is 4 days from Thursday
                        start_date = now.date() + timedelta(days=days_until_next_monday)
                        report["thoughts"].append(f"[Calendar Agent] Both Thursday and Friday have full-day events, suggesting next week instead: {start_date.strftime('%A, %B %d, %Y')}")
                    elif thursday_has_full_day:
                        # Thursday has full-day events, start from Friday
                        start_date = friday_date
                        report["thoughts"].append(f"[Calendar Agent] Today (Thursday) has full-day events, checking from Friday: {start_date.strftime('%A, %B %d, %Y')}")
                    else:
                        # Start from today (Thursday)
                        start_date = now.date()
                        report["thoughts"].append(f"[Calendar Agent] Checking from today (Thursday) for 'end of week': {start_date.strftime('%A, %B %d, %Y')}")
                else:  # Fri-Sun, check next week
                    days_until_next_thursday = (10 - today_weekday) % 7
                    next_thursday = now.date() + timedelta(days=days_until_next_thursday)
                    next_friday = next_thursday + timedelta(days=1)
                    
                    # Check if next Thursday has full-day events
                    thursday_events = calendar_api.get_events(next_thursday)
                    thursday_has_full_day = any(event["is_full_day"] for event in thursday_events)
                    
                    # Check if next Friday has full-day events
                    friday_events = calendar_api.get_events(next_friday)
                    friday_has_full_day = any(event["is_full_day"] for event in friday_events)
                    
                    if thursday_has_full_day and friday_has_full_day:
                        # Both next Thursday and Friday have full-day events
                        # Suggest Monday after next
                        days_until_monday_after_next = (14 - today_weekday) % 7
                        start_date = now.date() + timedelta(days=days_until_monday_after_next)
                        report["thoughts"].append(f"[Calendar Agent] Both next Thursday and Friday have full-day events, suggesting the week after: {start_date.strftime('%A, %B %d, %Y')}")
                    elif thursday_has_full_day:
                        # Next Thursday has full-day events, start from next Friday
                        start_date = next_friday
                        report["thoughts"].append(f"[Calendar Agent] Next Thursday has full-day events, checking from next Friday: {start_date.strftime('%A, %B %d, %Y')}")
                    else:
                        # Start from next Thursday
                        start_date = next_thursday
                        report["thoughts"].append(f"[Calendar Agent] 'End of week' requested after weekend. Checking from next Thursday: {start_date.strftime('%A, %B %d, %Y')}")
                
                # Add a warning about full-day events to the report
                if thursday_has_full_day or friday_has_full_day:
                    report["thoughts"].append(f"[Calendar Agent] Warning: Full-day events detected for end of week.")
            
            elif date_intent_type == "weekend":
                # Calculate coming Saturday
                today_weekday = now.weekday()
                days_until_saturday = (5 - today_weekday) % 7
                start_date = now.date() + timedelta(days=days_until_saturday)
                report["thoughts"].append(f"[Calendar Agent] 'Weekend' requested. Checking from {start_date.strftime('%A, %B %d, %Y')}")
            
            elif date_intent_type == "next_week":
                # Calculate next Monday
                days_until_next_monday = (7 - now.weekday()) % 7
                if days_until_next_monday == 0:
                    days_until_next_monday = 7  # If today is Monday, go to next Monday
                start_date = now.date() + timedelta(days=days_until_next_monday)
                report["thoughts"].append(f"[Calendar Agent] 'Next week' requested. Checking from {start_date.strftime('%A, %B %d, %Y')}")
            
            elif date_intent_type == "specific_day" or date_intent_type == "specific_date":
                # Use the LLM suggested date
                start_date = preferred_time.date()
                report["thoughts"].append(f"[Calendar Agent] Specific date ({start_date.strftime('%A, %B %d, %Y')}) requested.")
            
            else:
                # For any other intent type or custom date references, use LLM's suggestion
                start_date = preferred_time.date()
                report["thoughts"].append(f"[Calendar Agent] Using LLM suggested date: {start_date.strftime('%A, %B %d, %Y')}")
        else:
            # Default to next week if no specific date was requested
            days_until_next_monday = (7 - now.weekday()) % 7
            if days_until_next_monday == 0:
                days_until_next_monday = 7  # If today is Monday, go to next Monday
            next_monday = now.date() + timedelta(days=days_until_next_monday)
            
            # Start checking from next Monday
            start_date = next_monday
            report["thoughts"].append(f"[Calendar Agent] No specific date requested, defaulting to next week starting: {start_date.strftime('%A, %B %d, %Y')}")
        
        # For debugging
        report["thoughts"].append(f"[Calendar Agent] Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')} ({now.tzname()})")
        
        # Log the suggested date from the LLM
        report["thoughts"].append(f"[Calendar Agent] LLM suggested: {preferred_time.strftime('%A, %B %d, %Y at %I:%M %p %Z')} ({preferred_time.tzname()})")
        
        # Check multiple upcoming dates for availability (starting from next week)
        best_slot = None
        
        # Date exclusion list - dates that are fully booked with all-day events
        fully_booked_dates = []
        days_checked = 0
        
        # Check 7 days starting from next Monday
        for i in range(7):
            check_date = start_date + timedelta(days=i)
            formatted_date = check_date.strftime("%A, %B %d, %Y")
            date_str = check_date.strftime("%Y-%m-%d")
            
            # Get detailed events for this date
            events = calendar_api.get_events(check_date)
            
            # Check if there are any full-day events
            full_day_events = [event for event in events if event["is_full_day"]]
            
            # Log all events for debugging
            report["thoughts"].append(f"[Calendar Agent] Events for {formatted_date}:")
            event_details_for_date = []
            
            for event in events:
                event_type = "Full Day" if event["is_full_day"] else "Timed"
                event_info = f" - [{event_type}] {event['title']}: {event['start'].strftime('%H:%M')} to {event['end'].strftime('%H:%M')}"
                report["thoughts"].append(event_info)
                logging.info(event_info)
                event_details_for_date.append({
                    "title": event["title"],
                    "is_full_day": event["is_full_day"],
                    "start": event["start"].strftime("%H:%M"),
                    "end": event["end"].strftime("%H:%M")
                })
                
            # Store for displaying in UI
            report["event_details"][date_str] = event_details_for_date
            report["all_checked_dates"][date_str] = {
                "formatted_date": formatted_date,
                "has_full_day_events": len(full_day_events) > 0,
                "total_events": len(events)
            }
            
            # Use logging instead of print for better debug info
            logging.info(f"\n📅 Checking events for {formatted_date}")
            for event in events:
                event_type = "Full Day" if event["is_full_day"] else "Timed"
                logging.info(f" - [{event_type}] {event['title']}: {event['start'].strftime('%H:%M')} to {event['end'].strftime('%H:%M')}")
            
            # Get busy slots for this date
            busy_slots = calendar_api.get_busy_slots(check_date)
            
            # Check if this date is fully booked (e.g., has a full-day event)
            has_full_day_event = any((slot["end"] - slot["start"]).total_seconds() / 3600 > 12 for slot in busy_slots)
            
            # If we have full-day events, consider this date as fully booked
            if full_day_events or has_full_day_event:
                report["thoughts"].append(f"[Calendar Agent] Found full-day events on {formatted_date}, marking as fully booked")
                fully_booked_dates.append(check_date)
                
            # Store busy slots in our report
            report["all_checked_dates"][date_str]["busy_slots"] = [
                {
                    "start": slot["start"].strftime("%I:%M %p"),
                    "end": slot["end"].strftime("%I:%M %p")
                } 
                for slot in busy_slots
            ]
            
            # Skip slot checking if the date is fully booked with all-day events
            if check_date in fully_booked_dates:
                report["thoughts"].append(f"[Calendar Agent] Skipping {formatted_date} as it has full-day events or is fully booked")
                continue
                
            # Try to find a free slot on this day
            start_hour = 9  # Default start time
            
            # If this is the specifically requested date and time, use that time first
            if has_specific_date_request and check_date == preferred_time.date():
                start_hour = preferred_time.hour
                report["thoughts"].append(f"[Calendar Agent] Checking availability at the requested time: {start_hour}:00")
            
            test_time = datetime.combine(check_date, time(start_hour, 0)).replace(tzinfo=pytz.utc)
            free_slot = calendar_api.find_next_free_slot(
                preferred_start=test_time,
                duration_minutes=30,
                busy_slots=busy_slots
            )
            
            if free_slot:
                days_checked += 1
                report["thoughts"].append(f"[Calendar Agent] Found available slot on {formatted_date} at {free_slot.strftime('%I:%M %p')}")
                
                # If this is the first available slot we found, or if the initially preferred date matches this date
                if best_slot is None or check_date == preferred_time.date():
                    best_slot = free_slot
                    # If we found a slot on the initially preferred date, prioritize it
                    if check_date == preferred_time.date() and check_date not in fully_booked_dates:
                        report["thoughts"].append(f"[Calendar Agent] Prioritizing this slot as it matches the preferred date")
                        break  # Exit loop as we found a good match
            else:
                report["thoughts"].append(f"[Calendar Agent] No available slots on {formatted_date}")
        
        if best_slot:
            preferred_time = best_slot
            report["thoughts"].append(f"[Calendar Agent] Selected best available slot: {preferred_time.strftime('%A, %B %d, %Y at %I:%M %p')}")
        else:
            # If all dates in our range are fully booked, look further into the future
            if len(fully_booked_dates) > 0:
                report["thoughts"].append(f"[Calendar Agent] Found {len(fully_booked_dates)} fully booked dates. Looking for the next available date.")
                
                # Try the next 7 days beyond our initial range
                for i in range(7, 14):
                    check_date = start_date + timedelta(days=i)
                    formatted_date = check_date.strftime("%A, %B %d, %Y")
                    date_str = check_date.strftime("%Y-%m-%d")
                    
                    # Get events and check if there are any full-day events
                    events = calendar_api.get_events(check_date)
                    full_day_events = [event for event in events if event["is_full_day"]]
                    
                    if not full_day_events:
                        # Try to find a slot on this clear day
                        test_time = datetime.combine(check_date, time(9, 0)).replace(tzinfo=pytz.utc)
                        
                        # Get busy slots for this date
                        busy_slots = calendar_api.get_busy_slots(check_date)
                        
                        # Check if this date is fully booked
                        has_full_day_event = any((slot["end"] - slot["start"]).total_seconds() / 3600 > 12 for slot in busy_slots)
                        
                        if has_full_day_event:
                            continue
                            
                        free_slot = calendar_api.find_next_free_slot(
                            preferred_start=test_time,
                            duration_minutes=30,
                            busy_slots=busy_slots
                        )
                        
                        if free_slot:
                            preferred_time = free_slot
                            report["thoughts"].append(f"[Calendar Agent] Found slot beyond initial range: {preferred_time.strftime('%A, %B %d, %Y at %I:%M %p')}")
                            
                            # Add this date to our checked dates
                            report["event_details"][date_str] = [
                                {
                                    "title": event["title"],
                                    "is_full_day": event["is_full_day"],
                                    "start": event["start"].strftime("%H:%M"),
                                    "end": event["end"].strftime("%H:%M")
                                } 
                                for event in events
                            ]
                            
                            report["all_checked_dates"][date_str] = {
                                "formatted_date": formatted_date,
                                "has_full_day_events": len(full_day_events) > 0,
                                "total_events": len(events),
                                "busy_slots": [
                                    {
                                        "start": slot["start"].strftime("%I:%M %p"),
                                        "end": slot["end"].strftime("%I:%M %p")
                                    } 
                                    for slot in busy_slots
                                ]
                            }
                            break
            
            if not best_slot:  # If we still don't have a slot
                report["thoughts"].append("[Calendar Agent] No available time slots found. Unable to schedule meeting.")
                return {"calendar_done": False}
        
        # Double-check that the selected slot is actually free
        selected_date = preferred_time.date()
        selected_busy_slots = calendar_api.get_busy_slots(selected_date)
        
        # Verify the slot is free before creating the event
        slot_start = preferred_time
        slot_end = slot_start + timedelta(minutes=30)
        
        if not calendar_api.is_slot_free(slot_start, slot_end, selected_busy_slots):
            report["thoughts"].append(f"[Calendar Agent] WARNING: The selected slot is not free. This would cause overbooking.")
            # Try to find another slot on the same day
            alt_slot = calendar_api.find_next_free_slot(
                preferred_start=slot_start.replace(hour=9, minute=0),
                duration_minutes=30,
                busy_slots=selected_busy_slots
            )
            
            if alt_slot:
                preferred_time = alt_slot
                report["thoughts"].append(f"[Calendar Agent] Found alternative slot on same day: {preferred_time.strftime('%I:%M %p')}")
            else:
                report["thoughts"].append("[Calendar Agent] No alternative slots available. Cannot schedule meeting.")
                return {"calendar_done": False}
        
        # Store busy slots for the selected date in legacy format for compatibility
        report["busy_slots"] = [
            {
                "start": slot["start"].strftime("%A, %B %d, %Y at %I:%M %p"),
                "end": slot["end"].strftime("%A, %B %d, %Y at %I:%M %p")
            } 
            for slot in selected_busy_slots
        ]
        report["meeting_date"] = preferred_time.date().strftime("%A, %B %d, %Y")

        free_slot = calendar_api.find_next_free_slot(
            preferred_start=preferred_time,
            duration_minutes=30,
            busy_slots=selected_busy_slots
        )

        if not free_slot:
            report["thoughts"].append("[Calendar Agent] No available time slots found.")
            return {"calendar_done": False}

        print(f"✅ Found free slot: {free_slot}")

        event_link = calendar_api.create_event(
            summary=subject,
            description=f"Meeting ({mode}) with lead about: {subject}",
            start_time=free_slot,
            location="Zoom" if mode == "online" else "Office HQ – Lisbon"
        )

        confirmation = f"""Subject: Meeting Confirmation

Dear [Customer's Name],

I am writing to confirm our {mode} meeting about: '{subject}'.  
The meeting is scheduled for {free_slot.strftime("%A, %B %d, %Y at %I:%M %p")}.

If this time does not work for you, feel free to suggest an alternative.

📅 View Calendar Invite: {event_link}

Looking forward to it!

Best regards,  
[Your Name]"""

        memory.set("meeting", confirmation)
        report["tools_used"].append("CalendarTool.schedule + GoogleCalendarTool.create_event")
        thought, tokens = llm_think(f"Meeting confirmation for {lead['from']}:\n\n{confirmation}")
        report["thoughts"].append(f"[Calendar Agent] {thought}")
        report["tokens"] += tokens
        return {"calendar_done": True}

    def reply_node(state):
        lead = memory.get("lead")
        prompt = f"""Write a professional reply to the following lead message:

{lead['subject']}

Assume you are a sales assistant responding to a potential customer interested in your product or service."""
        thought, tokens = llm_think(prompt)
        report["thoughts"].append(f"[Reply Agent] {thought}")
        report["tokens"] += tokens
        memory.set("draft_reply", thought)
        report["tools_used"].append("LLM Reply Generator")
        return {"reply_done": True}

    builder = StateGraph(GraphState)
    builder.set_entry_point("coordinator")
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("calendar", calendar_node)
    builder.add_node("reply", reply_node)

    builder.add_edge("coordinator", "calendar")
    builder.add_edge("coordinator", "reply")
    builder.add_edge("calendar", END)
    builder.add_edge("reply", END)

    graph = builder.compile()
    result = graph.invoke({
        "lead_message": email_body,
        "lead_rule": lead_rule,
    })

    # Store the meeting confirmation in the report
    try:
        # Use get() method to safely check if meeting exists
        meeting_info = memory.get("meeting")
        if meeting_info:
            report["meeting"] = meeting_info
    except Exception as e:
        logging.error(f"Error retrieving meeting data: {e}")

    return report