from langgraph.graph import StateGraph, END
from memory.supabase_memory import memory
from tools.email_tool import EmailTool
from tools.calendar_tool import CalendarTool
from tools.google_calendar_tool import GoogleCalendarOAuthTool
from utils.llm import llm_think
from typing import TypedDict
import json
import datetime
import pytz
import os

# Define the state structure
class GraphState(TypedDict):
    lead_message: str
    lead_rule: str
    calendar_done: bool
    reply_done: bool

email_tool = EmailTool()
calendar_tool = CalendarTool()


def run_graph(email_body: str, lead_rule: str, access_token: str):
    report = {"thoughts": [], "tools_used": [], "tokens": 0}
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
            preferred_time = datetime.datetime.strptime(data["datetime"], "%A, %B %d, %Y at %I:%M %p")
            preferred_time = preferred_time.replace(tzinfo=pytz.utc)
            mode = data.get("mode", "online")
            subject = data.get("subject", "AI project discussion")
        except Exception as e:
            report["thoughts"].append(f"[Calendar Agent] Failed to parse meeting data: {e}")
            return {"calendar_done": False}

        busy_slots = calendar_api.get_busy_slots(preferred_time.date())

        print("\n📅 Busy slots for", preferred_time.date())
        for slot in busy_slots:
            print(f" - {slot['start']} to {slot['end']}")

        free_slot = calendar_api.find_next_free_slot(
            preferred_start=preferred_time,
            duration_minutes=30,
            busy_slots=busy_slots
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
    graph.invoke({
        "lead_message": email_body,
        "lead_rule": lead_rule,
    })

    return report