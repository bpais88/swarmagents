# 🧠 Lindy-Style Swarm of AI Agents

This project is a production-ready example of a multi-agent orchestration system using LangGraph, Streamlit, and real-world tools (like HubSpot CRM). It demonstrates how to build a modular swarm of AI agents that analyze emails, schedule meetings, and log interactions in CRMs — all with clear observability and extendability.

---

## 🚀 Features
- LangGraph for flexible stateful agent orchestration
- Modular tool/agent architecture inspired by CrewAI
- Real LLM-powered thought generation (GPT-4)
- Streamlit frontend for triggering and observing agent workflows
- Real HubSpot CRM integration with upsert logic
- Agent memory (mock or extendable to Supabase)
- Console-based observability of tools, thoughts, and token usage

---

## 📦 Project Structure

```bash
.
├── app.py                      # Streamlit frontend
├── orchestrator/
│   └── graph.py               # LangGraph definition + run_graph()
├── tools/
│   ├── email_tool.py         # EmailTool (mock)
│   ├── calendar_tool.py      # CalendarTool (mock)
│   └── hubspot_tool.py       # Real HubSpot CRM integration
├── utils/
│   └── llm.py                # LLM wrapper for thought generation
├── memory/
│   └── supabase_memory.py    # Mock memory store (can be extended)
├── .env                      # Your API keys and secrets
├── roadmap.md                # Project roadmap
└── README.md                 # You're here
```

---

## 🧪 Local Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create a `.env` file
```ini
OPENAI_API_KEY=sk-...
HUBSPOT_API_KEY=pat-...
```

### 3. Run it
```bash
streamlit run app.py
```

---

## 🧠 How It Works

### LangGraph
- Entry point: `coordinator_node` (reads and classifies email)
- Parallel branches: `calendar_node`, `crm_node`
- Final return: agent thoughts, tools used, tokens used

### Agents
- **Inbox Agent**: Analyzes the email and determines if it's a lead
- **Calendar Agent**: Schedules a meeting based on email
- **CRM Agent**: Logs the lead into HubSpot with contact & note (and upsert support)

### Memory
- In-memory `SupabaseMemory` mock implementation
- Easily extendable to real Supabase KV store or database logging

---

## ➕ How to Add a New Tool

1. Create `tools/your_tool.py`
```python
class YourTool:
    def do_something(self, data):
        return "result"
```

2. Import and instantiate it in `graph.py`
```python
from tools.your_tool import YourTool
your_tool = YourTool()
```

3. Add a node:
```python
def your_node(state):
    result = your_tool.do_something(state['some_data'])
    return {"your_step_done": True}

builder.add_node("your_step", your_node)
builder.add_edge("some_previous_step", "your_step")
```

4. Add to `GraphState` if needed

---

## ➕ How to Add a New Agent (LLM-Based)

1. Create a new node function with LLM call in `graph.py`:
```python
def agent_node(state):
    thought, tokens = llm_think("Some prompt")
    report["thoughts"].append(f"[New Agent] {thought}")
    report["tokens"] += tokens
    return {"agent_done": True}
```

2. Add it to the graph like above

---

## 📤 Deployment Checklist
- [ ] Add `.streamlit/secrets.toml` for OpenAI + HubSpot keys
- [ ] Push to GitHub
- [ ] Deploy to [Streamlit Cloud](https://streamlit.io/cloud)

---

## 🧠 Credits & Inspiration
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [CrewAI](https://github.com/joaomdmoura/crewAI)
- [HubSpot API](https://developers.hubspot.com/docs/api/crm/)

---

Happy swarming! 🤖