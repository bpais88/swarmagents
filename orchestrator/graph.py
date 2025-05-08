from langgraph.graph import StateGraph, END
from memory.supabase_memory import memory
from tools.email_tool import EmailTool
from tools.calendar_tool import CalendarTool
from tools.google_calendar_tool import GoogleCalendarOAuthTool
from utils.llm import llm_think
from utils.langfuse_logger import get_langfuse_handler
from typing import TypedDict, Optional, Annotated, Dict, Any
import json
from datetime import datetime, timedelta, date, time
import pytz
import os
import logging

# Import agent functions
from agents.inbox_agent import process_message
from agents.calendar_agent import schedule_meeting
from agents.crm_agent import log_lead
from agents.reply_agent import generate_reply

# --- Helper function & Reducer (DEFINED BEFORE GraphState) ---

def deep_merge_dicts(dict1, dict2):
    merged = dict1.copy()
    for key, value2 in dict2.items():
        if key in merged:
            value1 = merged[key]
            if isinstance(value1, dict) and isinstance(value2, dict):
                merged[key] = deep_merge_dicts(value1, value2)
            elif isinstance(value1, list) and isinstance(value2, list):
                merged[key] = value1 + value2
            elif isinstance(value1, (int, float)) and isinstance(value2, (int, float)) and \
                 ("tokens" in key.lower() or "time_ms" in key.lower() or key in ["input", "output", "total"]):
                 merged[key] = value1 + value2 
            else:
                merged[key] = value2
        else:
            merged[key] = value2
    return merged

def reduce_report_state(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    if left is None: return right
    if right is None: return left
    merged_report = left.copy()
    merged_report["thoughts"] = left.get("thoughts", []) + right.get("thoughts", [])
    merged_report["tools_used"] = left.get("tools_used", []) + right.get("tools_used", [])
    merged_report["meeting"] = right.get("meeting") if right.get("meeting") is not None else left.get("meeting")
    merged_report["error"] = right.get("error") if right.get("error") is not None else left.get("error")
    left_agent_thoughts = left.get("agent_thoughts", {})
    if not isinstance(left_agent_thoughts, dict): left_agent_thoughts = {}
    right_agent_thoughts = right.get("agent_thoughts", {})
    if not isinstance(right_agent_thoughts, dict): right_agent_thoughts = {}
    merged_agent_thoughts = left_agent_thoughts.copy()
    for agent, thoughts in right_agent_thoughts.items():
        if not isinstance(thoughts, list): thoughts = [str(thoughts)]
        merged_agent_thoughts[agent] = merged_agent_thoughts.get(agent, []) + thoughts
    merged_report["agent_thoughts"] = merged_agent_thoughts
    left_agent_metrics = left.get("agent_metrics", {})
    if not isinstance(left_agent_metrics, dict): left_agent_metrics = {}
    right_agent_metrics = right.get("agent_metrics", {})
    if not isinstance(right_agent_metrics, dict): right_agent_metrics = {}
    merged_agent_metrics = left_agent_metrics.copy()
    for agent, metrics_right in right_agent_metrics.items():
        if not isinstance(metrics_right, dict): continue
        metrics_left = merged_agent_metrics.get(agent, {})
        if not isinstance(metrics_left, dict): metrics_left = {}
        merged_agent_metrics[agent] = {
            "input_tokens": int(metrics_left.get("input_tokens", 0) or 0) + int(metrics_right.get("input", 0) or 0),
            "output_tokens": int(metrics_left.get("output_tokens", 0) or 0) + int(metrics_right.get("output", 0) or 0),
            "total_tokens": int(metrics_left.get("total_tokens", 0) or 0) + int(metrics_right.get("total", 0) or 0),
            "execution_time_ms": int(metrics_left.get("execution_time_ms", 0) or 0) + int(metrics_right.get("execution_time_ms", 0) or 0),
        }
    merged_report["agent_metrics"] = merged_agent_metrics
    global_input_tokens = 0
    global_output_tokens = 0
    global_total_tokens = 0
    for agent_metrics_data in merged_agent_metrics.values():
        if isinstance(agent_metrics_data, dict):
            global_input_tokens += int(agent_metrics_data.get("input_tokens", 0) or 0)
            global_output_tokens += int(agent_metrics_data.get("output_tokens", 0) or 0)
            global_total_tokens += int(agent_metrics_data.get("total_tokens", 0) or 0)
    merged_report["tokens"] = {
        "input": global_input_tokens,
        "output": global_output_tokens,
        "total": global_total_tokens
    }
    left_detailed = left.get("detailed_execution", {})
    if not isinstance(left_detailed, dict): left_detailed = {}
    right_detailed = right.get("detailed_execution", {})
    if not isinstance(right_detailed, dict): right_detailed = {}
    merged_report["detailed_execution"] = deep_merge_dicts(left_detailed, right_detailed)
    return merged_report

# --- State Definition (Simplified for non-interrupting graph) ---
class GraphState(TypedDict):
    lead_message: str
    lead_rule: Optional[str]
    access_token: Optional[str] 
    report: Annotated[Dict[str, Any], reduce_report_state] 
    
    # Flags/Data indicating completion of stages or data passing
    calendar_done: Optional[bool]
    crm_done: Optional[bool] 
    calendar_link: Optional[str]
    meeting_time: Optional[str]
    meeting_type: Optional[str]
    draft_reply: Optional[str] # Reply node output stored here

    error: Optional[str]

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

def inbox_node(state: GraphState):
    """Node to process the inbox message."""
    try:
        result = process_message(
            lead_message=state["lead_message"],
            lead_rule=state.get("lead_rule")
        )
        partial_report = {
            "thoughts": [result["thought"]],
            "tools_used": result.get("tools_used", []),
            "agent_thoughts": {"inbox_agent": [result["thought"]]} ,
            "agent_metrics": {"inbox_agent": result.get("tokens", {}).copy()}
        }
        return {"report": partial_report}
    except Exception as e:
        logging.error(f"Error in inbox_node: {e}", exc_info=True)
        return {"report": {"error": f"Inbox node error: {str(e)}"}}

def calendar_node(state: GraphState):
    """Node to schedule the meeting."""
    try:
        result = schedule_meeting(
            lead_message=state["lead_message"],
            access_token=state.get("access_token")
        )
        partial_report = {
            "thoughts": [result["thought"]],
            "tools_used": result.get("tools_used", []),
            "agent_thoughts": {"calendar_agent": [result["thought"]]} ,
            "agent_metrics": {"calendar_agent": result.get("tokens", {}).copy()}
        }
        output_state = {"report": partial_report, "calendar_done": True}
        if result.get("calendar_link"): output_state["calendar_link"] = result["calendar_link"]
        if result.get("meeting_time"): output_state["meeting_time"] = result["meeting_time"]
        if result.get("meeting_type"): output_state["meeting_type"] = result["meeting_type"]
        if result.get("error"): 
            partial_report["error"] = result["error"]
            partial_report["meeting"] = f"Failed to schedule: {result['error']}"
            output_state["error"] = result["error"]
        return output_state
    except Exception as e:
        logging.error(f"Error in calendar_node: {e}", exc_info=True)
        return {"report": {"error": f"Calendar node error: {str(e)}"}, "calendar_done": False}

def crm_node(state: GraphState):
    """Node to log lead to CRM."""
    try:
        result = log_lead(lead_message=state["lead_message"])
        partial_report = {
            "thoughts": [result["thought"]],
            "tools_used": result.get("tools_used", []),
            "agent_thoughts": {"crm_agent": [result["thought"]]} ,
            "agent_metrics": {"crm_agent": result.get("tokens", {}).copy()}
        }
        if result.get("error"): partial_report["error"] = result["error"]
        return {"report": partial_report, "crm_done": True}
    except Exception as e:
        logging.error(f"Error in crm_node: {e}", exc_info=True)
        return {"report": {"error": f"CRM node error: {str(e)}"}, "crm_done": False}

def reply_node(state: GraphState):
    """Node to generate the draft reply and store it in state."""
    try:
        meeting_info = {
            "calendar_link": state.get("calendar_link"),
            "meeting_time": state.get("meeting_time"),
            "meeting_type": state.get("meeting_type"),
            "error": state.get("report", {}).get("error") or state.get("error"),
            # No feedback passed via state in this non-looping version
        }
        # The generate_reply function saves to memory internally
        result = generate_reply(meeting_info=meeting_info) 
        partial_report = {
            "thoughts": [result["thought"]],
            "tools_used": result.get("tools_used", []),
            "agent_thoughts": {"reply_agent": [result["thought"]]} ,
            "agent_metrics": {"reply_agent": result.get("tokens", {}).copy()}
        }
        if result.get("error"): partial_report["error"] = result["error"]
        
        # Return the final reply content in the state
        return {
            "report": partial_report, 
            "draft_reply": result.get("reply") 
        }
    except Exception as e:
        logging.error(f"Error in reply_node: {e}", exc_info=True)
        return {"report": {"error": f"Reply node error: {str(e)}"}}

# --- Graph Definition (Simplified Edges) ---
def create_graph():
    """Creates the LangGraph StateGraph (no HITL interruption)."""
    builder = StateGraph(GraphState)
    builder.add_node("inbox", inbox_node)
    builder.add_node("calendar", calendar_node)
    builder.add_node("crm", crm_node) 
    builder.add_node("reply", reply_node)
    # REMOVED: builder.add_node("human_review", human_review_node)

    builder.set_entry_point("inbox")
    builder.add_edge("inbox", "calendar")
    builder.add_edge("inbox", "crm")
    builder.add_edge("calendar", "reply")
    builder.add_edge("crm", "reply") 
    # Reply node now goes directly to END
    builder.add_edge("reply", END) 
    
    # REMOVED: Conditional edge

    # Compile WITHOUT interruption
    return builder.compile()

# The run_graph function is NOT needed here, app.py uses create_graph and invoke