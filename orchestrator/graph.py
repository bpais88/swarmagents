from langgraph.graph import StateGraph, END
from memory.supabase_memory import memory
from tools.email_tool import EmailTool
from tools.calendar_tool import CalendarTool
from tools.hubspot_tool import HubSpotCRMTool
from utils.llm import llm_think
from typing import TypedDict

# Define the state structure
class GraphState(TypedDict):
    lead_email: str
    calendar_done: bool
    crm_done: bool

email_tool = EmailTool()
calendar_tool = CalendarTool()
crm_tool = HubSpotCRMTool()

def run_graph():
    report = {"thoughts": [], "tools_used": [], "tokens": 0}

    def coordinator_node(_):
        email = email_tool.read_email()
        report["tools_used"].append("EmailTool.read_email")
        thought, tokens = llm_think(f"Analyze this email and determine if it's a sales lead:\n\n{email}")
        report["thoughts"].append(f"[Inbox Agent] {thought}")
        report["tokens"] += tokens
        memory.set("lead", email)
        return {"lead_email": email["from"]}

    def calendar_node(state):
        email = state["lead_email"]
        result = calendar_tool.schedule(email)
        report["tools_used"].append("CalendarTool.schedule")
        memory.set("meeting", result)
        thought, tokens = llm_think(f"Meeting confirmation for {email}: {result}")
        report["thoughts"].append(f"[Calendar Agent] {thought}")
        report["tokens"] += tokens
        return {"calendar_done": True}

    def crm_node(state):
        lead = memory.get("lead")
    
    # 🛠️ Run the actual tool (HubSpot)
        result = crm_tool.log(lead)
        memory.set("crm_log", result)
        report["tools_used"].append("CRMTool.log")

    # 🧠 Optional: have the LLM reflect on what was logged
        thought, tokens = llm_think(f"The CRM tool returned the following result:\n\n{result}")
        report["thoughts"].append(f"[CRM Agent] {thought}")
        report["tokens"] += tokens

        return {"crm_done": True}

    builder = StateGraph(GraphState)
    builder.set_entry_point("coordinator")
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("calendar", calendar_node)
    builder.add_node("crm", crm_node)

    builder.add_edge("coordinator", "calendar")
    builder.add_edge("coordinator", "crm")

    builder.add_edge("calendar", END)
    builder.add_edge("crm", END)

    graph = builder.compile()
    graph.invoke({})

    return report
