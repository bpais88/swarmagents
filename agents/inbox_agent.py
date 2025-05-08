"""
Inbox Agent: Processes incoming messages, qualifies leads.
"""
from utils.llm import llm_think
from memory.supabase_memory import memory # Assuming this is the intended memory interface

def process_message(lead_message: str, lead_rule: str) -> dict:
    """Processes the lead message to qualify it based on the rule."""
    
    # Store basic email info in memory (as done in the original coordinator_node)
    email = {
        "from": "lead@example.com", # Mock sender
        "subject": lead_message
    }
    memory.set("lead", email)

    prompt = f"""
Use the following rule to decide if this is a qualified lead:
{lead_rule}

Here is the message from the lead:
{lead_message}

Provide your detailed reasoning and state clearly at the end if this is a qualified lead or not.
"""
    thought, tokens_data = llm_think(prompt)
    
    # Determine qualification status (optional, can be done in orchestrator if needed)
    # is_qualified = "qualified lead" in thought.lower() or "is a lead" in thought.lower()

    # Ensure tokens_data has the consistent dict structure
    if isinstance(tokens_data, dict):
        tokens = tokens_data
    else:
        tokens = {"input": 0, "output": 0, "total": int(tokens_data or 0)}

    return {
        "thought": f"[Inbox Agent] {thought}",
        # "is_qualified": is_qualified, # Can be returned if needed by graph logic
        "tokens": tokens,
        "tools_used": ["EmailTool.read_email"] # Tool used conceptually
    } 