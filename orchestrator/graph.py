from langgraph.graph import StateGraph, END
from memory.supabase_memory import memory
from tools.email_tool import EmailTool
from tools.calendar_tool import CalendarTool
from tools.google_calendar_tool import GoogleCalendarOAuthTool
from utils.llm import llm_think
from utils.langfuse_logger import get_langfuse_handler
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

# Initialize Langfuse handler
langfuse_handler = get_langfuse_handler()
trace = None  # Will store the active trace

email_tool = EmailTool()
calendar_tool = CalendarTool()

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

def run_graph(email_body: str, lead_rule: str, access_token: str):
    # Start a new trace for the entire workflow
    global trace
    if langfuse_handler:
        try:
            trace = langfuse_handler.trace(
                name="agent_workflow",
                metadata={
                    "email_length": len(email_body),
                    "rule_length": len(lead_rule),
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logging.warning(f"Failed to create Langfuse trace: {str(e)}")
            trace = None
        
    report = {"thoughts": [], "tools_used": [], "tokens": 0, "busy_slots": [], "all_checked_dates": {}, "event_details": {}}
    calendar_api = GoogleCalendarOAuthTool(access_token=access_token)

    def coordinator_node(state):
        global trace
        span = None
        if trace:
            try:
                span = trace.span(name="coordinator_node")
            except Exception as e:
                logging.warning(f"Failed to create coordinator span: {str(e)}")
            
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
        
        if span:
            add_observation_safely(
                span,
                name="coordinator_decision",
                value=1,
                metadata={"thought": thought, "tokens": tokens}
            )
        
        return {
            "lead_message": email["subject"],
            "lead_rule": state["lead_rule"]
        }

    def calendar_node(state):
        global trace
        span = None
        if trace:
            try:
                span = trace.span(name="calendar_node")
            except Exception as e:
                logging.warning(f"Failed to create calendar span: {str(e)}")
            
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
            
            # Parse the datetime string - handle both possible formats
            try:
                # Try the full format first (output by calendar_tool): "Saturday, April 26, 2025 at 10:00 AM"
                try:
                    preferred_time = datetime.strptime(datetime_str, "%A, %B %d, %Y at %I:%M %p")
                except ValueError:
                    # Fall back to the simpler format: "2025-04-26 10:00"
                    preferred_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                    
                # Add timezone info
                preferred_time = cet_timezone.localize(preferred_time)
                
                # Format for display
                formatted_time = preferred_time.strftime("%A, %B %d at %I:%M %p")
                
                report["thoughts"].append(f"[Calendar Agent] Scheduling event for {formatted_time}")
                report["tools_used"].append("GoogleCalendarTool.check_availability")
                report["event_details"]["datetime"] = formatted_time
                
                # Get additional event details from the data
                duration = int(data.get("duration", 30))
                report["event_details"]["duration"] = duration
                title = data.get("title", "Meeting")
                report["event_details"]["title"] = title
                description = data.get("description", "")
                report["event_details"]["description"] = description
                location = data.get("location", "")
                report["event_details"]["location"] = location
                
                # Create the calendar event
                meeting_link = calendar_api.create_event(
                    summary=title,
                    description=f"Meeting requested via: {lead_msg}\n\n{description}",
                    start_time=preferred_time,
                    duration_minutes=duration,
                    location=location
                )
                
                # Store the meeting link
                report["event_details"]["meeting_link"] = meeting_link
                report["thoughts"].append(f"[Calendar Agent] Created calendar event: {meeting_link}")
                
                if span:
                    add_observation_safely(
                        span,
                        name="calendar_scheduling",
                        value=1,
                        metadata={
                            "datetime": formatted_time,
                            "duration": duration,
                            "title": title,
                            "meeting_link": meeting_link
                        }
                    )
                
            except ValueError as e:
                report["thoughts"].append(f"[Calendar Agent] Error parsing datetime: {e}")
                if span:
                    add_observation_safely(
                        span,
                        name="calendar_error",
                        value=0,
                        metadata={"error": str(e), "datetime_str": datetime_str}
                    )
                
        except json.JSONDecodeError as e:
            report["thoughts"].append(f"[Calendar Agent] Error parsing calendar response: {e}")
            if span:
                add_observation_safely(
                    span,
                    name="calendar_error",
                    value=0,
                    metadata={"error": str(e), "raw_response": raw_json}
                )
            
        return {"calendar_done": True}

    def reply_node(state):
        global trace
        span = None
        if trace:
            try:
                span = trace.span(name="reply_node")
            except Exception as e:
                logging.warning(f"Failed to create reply span: {str(e)}")
        
        lead = memory.get("lead")
        
        # Check if we have event details to include in the reply
        event_context = ""
        if report["event_details"] and "datetime" in report["event_details"]:
            event_time = report["event_details"]["datetime"]
            event_title = report["event_details"].get("title", "Meeting")
            event_duration = report["event_details"].get("duration", 30)
            meeting_link = report["event_details"].get("meeting_link", "")
            
            event_context = f"""
I have scheduled a {event_duration} minute {event_title} for {event_time}.
"""
            if meeting_link:
                event_context += f"""
You can view and add this event to your calendar using this link: {meeting_link}
"""
            
            event_context += """
Please let me know if this time works for you, or if you would prefer a different time.
"""
        
        prompt = f"""Write a professional reply to the following lead message:

{lead['subject']}

{event_context}
Assume you are a sales assistant responding to a potential customer interested in your product or service.

If a meeting time has already been suggested in the context above, reference it in your reply instead of asking for a time preference.
If a calendar link is provided, mention it in your reply and encourage them to add it to their calendar.
"""
        thought, tokens = llm_think(prompt)
        report["thoughts"].append(f"[Reply Agent] {thought}")
        report["tokens"] += tokens
        memory.set("draft_reply", thought)
        report["tools_used"].append("LLM Reply Generator")
        
        if span:
            add_observation_safely(
                span,
                name="reply_generation",
                value=1,
                metadata={"reply_length": len(thought), "tokens": tokens}
            )
        
        return {"reply_done": True}

    # Build the graph
    builder = StateGraph(GraphState)

    # Add nodes
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("calendar", calendar_node)
    builder.add_node("reply", reply_node)

    # Add edges
    builder.add_edge("coordinator", "calendar")
    builder.add_edge("calendar", "reply")
    builder.add_edge("reply", END)

    # Set the entry point
    builder.set_entry_point("coordinator")

    # Compile the graph
    graph = builder.compile()

    # Run the graph with the new API
    config = {
        "lead_message": email_body,
        "lead_rule": lead_rule,
        "calendar_done": False,
        "reply_done": False
    }
    for _ in graph.stream(config):
        pass  # Process each state if needed
    
    if trace:
        try:
            add_observation_safely(
                trace,
                name="workflow_completion",
                value=1,
                metadata={
                    "total_tokens": report["tokens"],
                    "total_thoughts": len(report["thoughts"]),
                    "tools_used": report["tools_used"]
                }
            )
            if hasattr(trace, "end"):
                trace.end()
        except Exception as e:
            logging.warning(f"Failed to end Langfuse trace: {str(e)}")

    return report