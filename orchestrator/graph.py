from langgraph.graph import StateGraph, END
from memory.supabase_memory import memory
from tools.email_tool import EmailTool
from tools.calendar_tool import CalendarTool
from tools.hubspot_tool import HubSpotCRMTool
from utils.llm import llm_think
from typing import TypedDict

# Define the state structure
class GraphState(TypedDict):
    lead_message: str
    lead_rule: str
    calendar_done: bool
    crm_done: bool
    reply_done: bool

email_tool = EmailTool()
calendar_tool = CalendarTool()
crm_tool = HubSpotCRMTool()

def run_graph(email_body: str, lead_rule: str):
    report = {"thoughts": [], "tools_used": [], "tokens": 0}

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
        email = state["lead_message"]
        result = calendar_tool.schedule(email)
        report["tools_used"].append("CalendarTool.schedule")
        memory.set("meeting", result)
        thought, tokens = llm_think(f"Meeting confirmation for {email}: {result}")
        report["thoughts"].append(f"[Calendar Agent] {thought}")
        report["tokens"] += tokens
        return {"calendar_done": True}

    def crm_node(state):
        lead = memory.get("lead")
        result = crm_tool.log(lead)
        report["tools_used"].append("CRMTool.log")
        memory.set("crm_log", result)
        thought, tokens = llm_think(f"The CRM tool returned the following result:\n\n{result}")
        report["thoughts"].append(f"[CRM Agent] {thought}")
        report["tokens"] += tokens
        return {"crm_done": True}

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
    builder.add_node("crm", crm_node)
    builder.add_node("reply", reply_node)

    builder.add_edge("coordinator", "calendar")
    builder.add_edge("coordinator", "crm")
    builder.add_edge("coordinator", "reply")
    builder.add_edge("calendar", END)
    builder.add_edge("crm", END)
    builder.add_edge("reply", END)

    graph = builder.compile()
    graph.invoke({
        "lead_message": email_body,
        "lead_rule": lead_rule,
    })

    return report
