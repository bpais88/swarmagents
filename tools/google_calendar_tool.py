import os
import json
import datetime
import pytz
import logging
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

load_dotenv()

class GoogleCalendarOAuthTool:
    def __init__(self, access_token: str):
        """Initializes the tool using a pre-obtained OAuth access token."""
        if not access_token:
            raise ValueError("Access token is required for GoogleCalendarOAuthTool")

        # Create credentials directly from the access token
        # Note: This assumes the token is valid and has the correct scopes.
        # For refresh tokens, a more complex credential handling would be needed.
        try:
            credentials = Credentials(token=access_token)
            # Check if token is valid/expired (optional but good practice)
            # if credentials.expired and credentials.refresh_token:
            #     credentials.refresh(Request())
            # elif credentials.expired:
            #     raise ValueError("Access token is expired and no refresh token available.")

            self.service = build("calendar", "v3", credentials=credentials)
        except Exception as e:
            # Catch potential issues with building the service or invalid token format
            logging.error(f"Failed to build Google Calendar service with token: {e}")
            raise ValueError(f"Failed to initialize Google Calendar service: {e}")

        self.calendar_id = "primary"

    def get_events(self, date: datetime.date):
        """Get detailed event information for a specific date including titles and full-day events."""
        start_time = datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=pytz.utc)
        end_time = datetime.datetime.combine(date, datetime.time.max).replace(tzinfo=pytz.utc)
        
        try:
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            parsed_events = []
            
            # Debug output
            logging.info(f"RAW events data for {date}: {events}")
            
            for event in events:
                try:
                    start = event.get('start', {})
                    end = event.get('end', {})
                    
                    # Handle full-day events (they have 'date' instead of 'dateTime')
                    is_full_day = 'date' in start
                    
                    if is_full_day:
                        # Full-day event spans the entire day
                        start_dt = datetime.datetime.fromisoformat(start.get('date')).replace(
                            hour=0, minute=0, second=0).replace(tzinfo=pytz.utc)
                        end_dt = datetime.datetime.fromisoformat(end.get('date')).replace(
                            hour=23, minute=59, second=59).replace(tzinfo=pytz.utc)
                    else:
                        # Regular event with specific times
                        start_dt = datetime.datetime.fromisoformat(start.get('dateTime').replace('Z', '+00:00'))
                        end_dt = datetime.datetime.fromisoformat(end.get('dateTime').replace('Z', '+00:00'))
                    
                    # Log each event we're processing
                    logging.info(f"Processing event: '{event.get('summary')}', full day: {is_full_day}, start: {start_dt}, end: {end_dt}")
                    
                    parsed_events.append({
                        "title": event.get('summary', 'Untitled Event'),
                        "start": start_dt,
                        "end": end_dt,
                        "is_full_day": is_full_day,
                        "link": event.get('htmlLink', '')
                    })
                except Exception as e:
                    logging.warning(f"Couldn't parse event: {e}")
            
            return parsed_events
        except Exception as e:
            logging.error(f"Error fetching events: {e}")
            return []
            
    def get_busy_slots(self, date: datetime.date):
        """Get busy time slots for a specific date using the freebusy query."""
        start_time = datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=pytz.utc)
        end_time = datetime.datetime.combine(date, datetime.time.max).replace(tzinfo=pytz.utc)

        # First get all events to handle full-day events properly
        events = self.get_events(date)
        
        # Create busy slots from all events
        manual_busy_slots = []
        has_full_day_events = False
        
        for event in events:
            # If there's a full-day event, mark the entire day as busy
            if event["is_full_day"]:
                has_full_day_events = True
                logging.info(f"Full day event detected on {date}: {event['title']}")
                # For full day events, create a slot for the entire day
                manual_busy_slots.append({
                    "start": start_time,
                    "end": end_time
                })
                break  # One full-day event makes the entire day busy
            else:
                manual_busy_slots.append({
                    "start": event["start"],
                    "end": event["end"]
                })
        
        # If we already detected full-day events, no need for the API call
        if has_full_day_events:
            logging.info(f"Day {date} is fully booked with full-day events")
            return manual_busy_slots
            
        # Otherwise, also use the freebusy API as a backup
        body = {
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "items": [{"id": self.calendar_id}],
            "timeZone": "UTC"
        }

        try:
            response = self.service.freebusy().query(body=body).execute()
            busy = response.get("calendars", {}).get(self.calendar_id, {}).get("busy", [])
            
            # Log the raw API response
            logging.info(f"FreeBusy API response for {date}: {busy}")
            
            api_slots = []
            for slot in busy:
                try:
                    api_slots.append({
                        "start": datetime.datetime.fromisoformat(slot["start"].replace("Z", "+00:00")),
                        "end": datetime.datetime.fromisoformat(slot["end"].replace("Z", "+00:00")),
                    })
                except Exception as e:
                    logging.warning(f"Couldn't parse busy slot: {e}")
            
            # Combine manually extracted events with the API response
            combined_slots = manual_busy_slots + api_slots
            
            # Deduplicate and merge overlapping slots
            if combined_slots:
                combined_slots.sort(key=lambda x: x["start"])
                merged_slots = [combined_slots[0]]
                
                for current in combined_slots[1:]:
                    previous = merged_slots[-1]
                    # If current slot overlaps with previous slot, merge them
                    if current["start"] <= previous["end"]:
                        previous["end"] = max(previous["end"], current["end"])
                    else:
                        merged_slots.append(current)
                        
                return merged_slots
            
            return combined_slots
            
        except Exception as e:
            logging.error(f"Error fetching busy slots: {e}")
            # Fall back to the manually created list
            return manual_busy_slots

    def is_slot_free(self, start: datetime.datetime, end: datetime.datetime, busy_slots):
        """Check if a time slot is free (not overlapping with any busy slots)."""
        for slot in busy_slots:
            # If there's any overlap between the proposed slot and a busy slot
            if slot["start"] < end and start < slot["end"]:
                logging.info(f"Slot conflict detected: {start} to {end} conflicts with {slot['start']} to {slot['end']}")
                return False
        logging.info(f"Slot is free: {start} to {end}")
        return True

    def find_next_free_slot(self, preferred_start: datetime.datetime, duration_minutes=30, busy_slots=[]):
        """Find the next available time slot starting from a preferred time."""
        logging.info(f"🔎 Searching for free slot starting from: {preferred_start}")

        # First check if there are any full-day events that block the entire day
        for slot in busy_slots:
            # If a slot spans the entire day or most of it (>12 hours), consider the day fully booked
            slot_duration = (slot["end"] - slot["start"]).total_seconds() / 3600
            if slot_duration > 12:
                logging.info(f"Day appears to be fully booked with a long event ({slot_duration} hours)")
                return None

        for offset_days in range(0, 7):  # Look ahead 1 week from preferred
            current_day = preferred_start + datetime.timedelta(days=offset_days)
            current_date = current_day.date()
            
            # Skip to the next day if we're not on the first iteration
            if offset_days > 0:
                current_day = current_day.replace(hour=9, minute=0, second=0, microsecond=0)
            
            # Get fresh busy slots for this specific day to ensure we have the most accurate data
            if offset_days > 0:  # Only if we're looking at a different day
                day_busy_slots = self.get_busy_slots(current_date)
                # If we detect a full-day event, skip this day entirely
                if any((slot["end"] - slot["start"]).total_seconds() / 3600 > 12 for slot in day_busy_slots):
                    logging.info(f"Skipping {current_date} due to full-day events")
                    continue
            else:
                day_busy_slots = busy_slots
            
            # Check each hour from 9 AM to 5 PM
            for hour in range(9, 17):  # Working hours
                # Skip hours earlier than our current time if we're checking today
                if current_date == preferred_start.date() and hour < preferred_start.hour:
                    continue
                    
                # Try each hour
                start = current_day.replace(hour=hour, minute=0, second=0, microsecond=0)
                end = start + datetime.timedelta(minutes=duration_minutes)

                if self.is_slot_free(start, end, day_busy_slots):
                    logging.info(f"✅ Found available slot: {start}")
                    return start

        logging.warning("❌ No available slot found")
        return None

    def create_event(self, summary: str, description: str, start_time: datetime.datetime, duration_minutes=30, location=""):
        end_time = start_time + datetime.timedelta(minutes=duration_minutes)

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": start_time.tzname() or "UTC",
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": end_time.tzname() or "UTC",
            },
            "location": location,
        }

        created = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
        logging.info(f"📅 Created event: {created.get('htmlLink')}")
        return created.get("htmlLink")