# �� Swarm of AI Agents (Early Version - b22c40c)

This project demonstrates an early concept for a multi-agent system using LangGraph and Streamlit. At this stage, it primarily focuses on processing an incoming email message, attempting to schedule a meeting via Google Calendar based on the email content, and generating a reply.

---

## ✨ Core Concepts Demonstrated

*   **LangGraph Orchestration**: Uses LangGraph to define a sequence of operations (nodes).
*   **Streamlit Frontend**: Provides a basic web UI for inputting an email body and a qualification rule.
*   **Google Calendar Integration**: Includes tools and OAuth flow to connect to Google Calendar for scheduling.
*   **LLM Integration**: Utilizes an LLM (via `utils/llm.py`) for analyzing text and generating replies.
*   **Modular Tools**: Contains separate files for interacting with external services (Google Calendar, potentially others like Email, HubSpot - though integration might be basic at this stage).
*   **Basic Memory**: Includes a simple memory mechanism (`memory/supabase_memory.py`, though Supabase integration might be minimal/placeholder).

---

## 📦 Project Structure (at commit b22c40c)

```bash
.
├── app.py                # Streamlit frontend (UI, OAuth, workflow trigger)
├── orchestrator/
│   └── graph.py          # LangGraph definition + run_graph() function
├── tools/
│   ├── email_tool.py        # Mock/Basic Email Tool
│   ├── calendar_tool.py     # Helper tool potentially used by GoogleCalendarOAuthTool
│   ├── google_calendar_tool.py # Tool for Google Calendar API interaction (OAuth)
│   ├── google_gmail_tool.py  # Tool for Gmail (likely unused/incomplete)
│   └── hubspot_tool.py      # Tool for HubSpot (likely unused/incomplete)
├── utils/
│   ├── llm.py               # LLM wrapper (e.g., OpenAI)
│   └── langfuse_logger.py   # Langfuse integration for tracing (optional)
├── memory/
│   └── supabase_memory.py   # Basic memory store concept
├── .env.example          # Example environment variables
├── requirements.txt      # Python dependencies
├── .devcontainer/        # Dev container configuration
│   └── devcontainer.json
└── README.md             # This file
```

---

## ⚙️ Workflow Overview (Conceptual at this stage)

1.  **Input**: User provides an email body and a qualification rule via the Streamlit UI.
2.  **OAuth**: User authorizes access to their Google Calendar.
3.  **Orchestration (`run_graph`)**:
    *   **Coordinator/Inbox Node**: Reads the email, potentially uses the rule and LLM to classify it (details might be in `graph.py`). Stores info in memory.
    *   **Calendar Node**: Attempts to parse the email for scheduling intent. Interacts with `GoogleCalendarOAuthTool` to check availability and create an event on the user's authorized calendar. Stores results (link, time) in memory/report.
    *   **Reply Node**: Uses an LLM to generate a reply based on the input email and the outcome of the calendar scheduling step. Stores the draft reply in memory.
4.  **Output**: Streamlit UI displays agent thoughts, tools used (as reported by the graph), token counts, the draft reply, and details about the calendar scheduling attempt.

**(Note:** The exact implementation and interaction between nodes are defined within `orchestrator/graph.py` at this commit.)

---

## 🛠️ Key Components & Purpose

*   **`app.py`**:
    *   **Purpose**: User Interface and primary interaction point.
    *   **Responsibilities**: Handles Google OAuth flow, collects user input (email, rule), triggers the `run_graph` function, displays the results and diagnostic information.
*   **`orchestrator/graph.py`**:
    *   **Purpose**: Defines the core agent workflow logic.
    *   **Responsibilities**: Uses LangGraph to define the sequence of agent steps (nodes) and state transitions. Contains the node functions (`coordinator_node`, `calendar_node`, `reply_node` in the older code version) that call tools and LLMs. Manages the overall state (`GraphState`) and accumulates results into a `report`.
*   **`tools/google_calendar_tool.py`**:
    *   **Purpose**: Interface with the Google Calendar API.
    *   **Responsibilities**: Uses the OAuth `access_token` to perform actions like checking calendar availability (`get_busy_times`, `find_available_slots`) and creating calendar events (`create_event`). May rely on `tools/calendar_tool.py` for LLM-based parsing of scheduling requests within emails.
*   **`tools/calendar_tool.py`**:
    *   **Purpose**: Higher-level calendar logic, likely involving LLM interaction.
    *   **Responsibilities**: Potentially uses an LLM to parse natural language requests (e.g., "meeting next Tuesday at 3pm") from the lead email into structured data (date, time, duration) needed by `google_calendar_tool.py`.
*   **`tools/email_tool.py` / `google_gmail_tool.py` / `hubspot_tool.py`**:
    *   **Purpose**: Placeholder or early versions for interacting with Email/Gmail/HubSpot.
    *   **Responsibilities**: Likely contain basic classes or functions, but may not be fully integrated into the main workflow defined in `graph.py` at this specific commit.
*   **`utils/llm.py`**:
    *   **Purpose**: Abstract interaction with a Large Language Model (LLM).
    *   **Responsibilities**: Sends prompts to the configured LLM (e.g., OpenAI GPT models) and returns the generated text/thoughts and token counts. Handles API key management.
*   **`memory/supabase_memory.py`**:
    *   **Purpose**: Simple key-value store concept.
    *   **Responsibilities**: Provides basic `get` and `set` functions. At this stage, it might be a simple in-memory dictionary or a very basic Supabase placeholder, not necessarily a fully functional persistent memory.

---

## 🚀 Running the Application (at commit b22c40c)

### 1. Prerequisites
*   Python 3.x
*   `pip`

### 2. Setup Environment
*   Clone the repository and checkout commit `b22c40c`:
    ```bash
    git clone <repository_url>
    cd <repository_name>
    git checkout b22c40c4af8930a1d17122879ea45a16bc47fa42
    ```
*   Install dependencies:
    ```bash
    pip3 install --user -r requirements.txt
    pip3 install --user streamlit # Ensure streamlit is installed
    ```
*   Create a `.env` file (copy from `.env.example` if it exists, or create manually):
    ```ini
    OPENAI_API_KEY=sk-... # Your OpenAI API Key
    # Google OAuth Credentials (Generate from Google Cloud Console)
    GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com
    GOOGLE_CLIENT_SECRET=YOUR_GOOGLE_CLIENT_SECRET
    # Ensure this matches the Authorized Redirect URI in your Google Cloud credentials
    GOOGLE_REDIRECT_URI=http://localhost:8501
    # Optional: Langfuse credentials if using tracing
    # LANGFUSE_SECRET_KEY=sk_lf_...
    # LANGFUSE_PUBLIC_KEY=pk_lf_...
    # LANGFUSE_HOST=https://cloud.langfuse.com
    ```
    *   **Important:** You MUST create Google OAuth 2.0 credentials (Web Application type) in the Google Cloud Console. Add `http://localhost:8501` (or the port Streamlit uses) to the "Authorized redirect URIs". Put the Client ID and Client Secret in your `.env` file.

### 3. Run Streamlit
```bash
streamlit run app.py
```
*   The app should open in your browser (usually at `http://localhost:8501`).
*   You will need to click "Authorize Google Calendar" and go through the Google OAuth flow the first time.
*   Enter an email body and rule, then click "Run Agent Workflow".

---

This README provides a snapshot of the project's state and capabilities at commit `b22c40c`.