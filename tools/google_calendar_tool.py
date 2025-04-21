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

    def get_busy_slots(self, date: datetime.date):
        start_time = datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=pytz.utc)
        end_time = datetime.datetime.combine(date, datetime.time.max).replace(tzinfo=pytz.utc)

        body = {
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "items": [{"id": self.calendar_id}],
            "timeZone": "UTC"
        }

        try:
            response = self.service.freebusy().query(body=body).execute()
            busy = response.get("calendars", {}).get(self.calendar_id, {}).get("busy", [])
            parsed = []
            for slot in busy:
                try:
                    parsed.append({
                        "start": datetime.datetime.fromisoformat(slot["start"].replace("Z", "+00:00")),
                        "end": datetime.datetime.fromisoformat(slot["end"].replace("Z", "+00:00")),
                    })
                except Exception:
                    logging.warning(f"Couldn't parse busy slot: {slot}")
            return parsed
        except Exception as e:
            logging.error(f"Error fetching busy slots: {e}")
            return []

    def is_slot_free(self, start: datetime.datetime, end: datetime.datetime, busy_slots):
        for slot in busy_slots:
            if slot["start"] < end and start < slot["end"]:
                return False
        return True

    def find_next_free_slot(self, preferred_start: datetime.datetime, duration_minutes=30, busy_slots=[]):
        logging.info(f"🔎 Searching for free slot starting from: {preferred_start}")

        for offset_days in range(0, 7):  # Look ahead 1 week from preferred
            current_day = preferred_start + datetime.timedelta(days=offset_days)
            for hour in range(9, 17):  # Working hours
                start = current_day.replace(hour=hour, minute=0, second=0, microsecond=0)
                end = start + datetime.timedelta(minutes=duration_minutes)

                if self.is_slot_free(start, end, busy_slots):
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