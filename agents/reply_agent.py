"""
Reply Agent: Generates email replies based on workflow outcomes.
"""
import logging
from utils.llm import llm_think
from memory.supabase_memory import memory # Assuming this is the intended memory interface

def generate_reply(meeting_info: dict = None) -> dict:
    """Generates a reply email based on meeting info (or lack thereof)."""
    
    if meeting_info is None: 
        meeting_info = {}
        
    # Attempt to retrieve lead subject from memory for context
    lead_subject = "your recent inquiry" # Default subject
    try:
        lead = memory.get("lead")
        if lead and isinstance(lead, dict):
            lead_subject = lead.get("subject", lead_subject)
    except Exception as e:
        logging.warning(f"Could not retrieve lead subject from memory: {e}")

    # Determine context based on meeting_info
    event_context = ""
    thought_summary = ""
    user_feedback_prompt = ""

    # Check for feedback (for revision)
    if meeting_info.get("user_feedback"):
        user_feedback_prompt = f"\nPlease revise the previous draft based on this feedback: {meeting_info['user_feedback']}"
        thought_summary = "Revising draft based on feedback. " # Prepend to final thought

    # Check for successful scheduling first
    if meeting_info.get("calendar_link") and meeting_info.get("meeting_time") and not meeting_info.get("error"):
        event_time = meeting_info["meeting_time"]
        meeting_link = meeting_info["calendar_link"]
        event_title = meeting_info.get("title", "Meeting") 
        event_duration = meeting_info.get("duration", 30)

        event_context = (
            f"I have scheduled a {event_duration}-minute {event_title} for {event_time}.\n\n"
            f"You can view and add this event to your calendar using this link: {meeting_link}\n\n"
            f"Please let me know if this time works for you, or if you would prefer a different time."
        )
        thought_summary += "Generated reply confirming scheduled meeting."

    elif meeting_info.get("error"):
        # Error during scheduling (includes conflicts)
        error = meeting_info['error']
        event_context = (
            f"Unfortunately, I encountered an issue while trying to schedule the meeting: {error}\n\n"
            f"Could you please suggest another time or provide more details?"
        )
        thought_summary += f"Generated reply indicating scheduling error: {error}."

    else:
        # Fallback: No meeting scheduled, no error
        event_context = (
            f"I wasn't able to automatically confirm a meeting time based on our previous conversation.\n\n"
            f"Could you please suggest a specific date and time that works well for you?"
        )
        thought_summary += "Generated reply asking for scheduling clarification."

    # Construct the final prompt
    prompt = (
        f"Write a professional reply regarding: {lead_subject}\n\n"
        f"{event_context}\n\n"
        f"Assume you are a helpful assistant responding to the initial request.\n"
        f"Keep the tone friendly and professional. "
        f"If a meeting was scheduled, confirm the details clearly. "
        f"If there was an error or no time was found, explain briefly and ask for clarification or alternative times."
        f"{user_feedback_prompt}" # Append feedback instruction if present
    )
    
    reply_text, tokens_data = llm_think(prompt)
    
    # Store the draft reply in memory
    try:
        memory.set("draft_reply", reply_text)
    except Exception as e:
        logging.error(f"Failed to set draft_reply in memory: {e}")

    # Ensure tokens_data has the consistent dict structure
    if isinstance(tokens_data, dict):
        tokens = tokens_data
    else:
        tokens = {"input": 0, "output": 0, "total": int(tokens_data or 0)}

    return {
        "thought": f"[Reply Agent] {thought_summary.strip()}", # Use generated summary
        "reply": reply_text,
        "tokens": tokens,
        "tools_used": ["LLM Reply Generator"]
    } 