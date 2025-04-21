import streamlit as st
from orchestrator.graph import run_graph
from memory.supabase_memory import memory
from urllib.parse import urlencode
import os
import requests
import logging
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Set up logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Initialize session state for OAuth flow
if "oauth_complete" not in st.session_state:
    st.session_state.oauth_complete = False
if "access_token" not in st.session_state:
    st.session_state.access_token = None

st.set_page_config(page_title="Lindy-style Swarm of Agents", layout="centered")
st.title("Lindy-style Swarm of Agents")

# Check for reset request
reset_oauth = st.query_params.get("reset")
if reset_oauth == "true":
    st.session_state.oauth_complete = False
    st.session_state.access_token = None
    st.query_params.clear()
    st.success("OAuth state reset. Please authorize again.")
    logging.info("OAuth state has been reset.")
    st.stop()

# OAuth credentials from .env
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")

# Use the actual Streamlit URL to handle port changes
ACTUAL_REDIRECT_URI = f"http://localhost:{st.get_option('server.port')}"

# Sanity check logging
logging.info(f"Client ID: {CLIENT_ID}")
logging.info(f"Configured Redirect URI: {REDIRECT_URI}")
logging.info(f"Actual Streamlit Redirect URI: {ACTUAL_REDIRECT_URI}")

# Step 1: Construct OAuth URL
def get_auth_url():
    params = urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": ACTUAL_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true"
    })
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    logging.info(f"Generated Google OAuth URL: {auth_url}")
    return auth_url

# Step 2: Detect redirect w/ code param
code = st.query_params.get("code")

# Check if we already have a valid access token in session
if st.session_state.oauth_complete and st.session_state.access_token:
    st.success("Google Calendar is connected!")
    st.info("You can now use the agent workflow below.")
elif not code:
    st.markdown("### Connect your Google Calendar")
    auth_link = get_auth_url()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.link_button("Authorize Google Calendar", auth_link)
    with col2:
        reset_url = f"{ACTUAL_REDIRECT_URI}?reset=true"
        st.link_button("Reset Auth", reset_url)
    logging.info("Waiting for user to authorize via Google")
    st.stop()
elif not st.session_state.oauth_complete:
    # Step 3: Exchange code for access_token (only if we haven't done it already)
    logging.info("OAuth code received. Exchanging for token...")
    logging.info(f"Code value (first 10 chars): {code[:10]}...")

    # Clear browser cache warning
    st.warning("If you're seeing authorization errors, try clearing your browser cache or using incognito mode.")
    st.info("Currently processing your authorization...")

    # Prepare token exchange request
    token_data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": ACTUAL_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    # Add headers for token request
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logging.info(f"Token exchange data: client_id={CLIENT_ID[:8]}..., redirect_uri={ACTUAL_REDIRECT_URI}")

    try:
        # Make token exchange request with proper headers
        token_response = requests.post("https://oauth2.googleapis.com/token", data=token_data, headers=headers)
        
        if token_response.status_code != 200:
            st.error("Failed to exchange token with Google.")
            logging.error(f"Token exchange failed: {token_response.text}")
            logging.error(f"Full token exchange response: Status={token_response.status_code}, Headers={dict(token_response.headers)}")
            st.stop()
        
        # Parse the response
        token_json = token_response.json()
        access_token = token_json.get("access_token")
        
        if not access_token:
            st.error("No access token found in response")
            logging.error(f"No access token in response: {token_json}")
            st.stop()
            
        logging.info("Access token retrieved successfully.")
        st.session_state.oauth_complete = True
        st.session_state.access_token = access_token
        
    except Exception as e:
        st.error(f"Error during token exchange: {str(e)}")
        logging.error(f"Exception during token exchange: {str(e)}")
        st.stop()

# ----------------------------
# Run Agent Workflow
# ----------------------------

st.markdown("""
Trigger the AI agent workflow to process a lead email, schedule a meeting, and log it into CRM.
You can provide the lead email and the rule for how the agent should classify it.
""")

lead_text = st.text_area("Paste Lead Email", height=200)
lead_rule = st.text_input(
    "Lead Qualification Rule",
    value="Consider it a lead if the sender asks for a meeting, demo, or pricing."
)

if st.button("Run Agent Workflow") and lead_text:
    with st.spinner("Running agents..."):
        report = run_graph(email_body=lead_text, lead_rule=lead_rule, access_token=st.session_state.access_token)

    st.success("Workflow completed!")
    
    # DEBUG: Print report structure
    st.json(report)

    st.subheader("Agent Thoughts")
    for thought in report["thoughts"]:
        st.markdown(f"- {thought}")

    st.subheader("Tools Used")
    for tool in report["tools_used"]:
        st.markdown(f"- {tool}")

    st.subheader("Total Tokens Used")
    st.markdown(f"**Tokens**: {report['tokens']}")

    st.subheader("Draft Reply Email")
    reply = memory.get("draft_reply")
    if reply:
        st.code(reply, language="markdown")
    else:
        st.markdown("_No reply was generated._")

    if "meeting" in report:
        st.subheader("Meeting Confirmation")
        st.markdown(report["meeting"])
        
        # Display detailed calendar events for debugging
        if "event_details" in report and report["event_details"]:
            st.subheader("Your Calendar Events")
            
            st.markdown("""
            The agent checked your Google Calendar for the next few days to find the best meeting time.
            Below are all the events in your calendar that were considered during scheduling.
            """)
            
            # Create tabs for each checked date
            date_tabs = st.tabs([date_info["formatted_date"] for date_str, date_info in sorted(report["event_details"].items())])
            
            for i, (date_str, date_info) in enumerate(sorted(report["event_details"].items())):
                with date_tabs[i]:
                    formatted_date = date_info["formatted_date"]
                    events = date_info["events"]
                    
                    if events:
                        # Create a colorful table of events
                        event_table = """
                        <table style="width:100%; border-collapse: collapse;">
                            <tr style="background-color: #f0f0f0;">
                                <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Event</th>
                                <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Time</th>
                                <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Type</th>
                            </tr>
                        """
                        
                        for j, event in enumerate(events):
                            # Alternate row colors
                            row_color = "#f9f9f9" if j % 2 == 0 else "white"
                            # Highlight full-day events
                            if event["is_full_day"]:
                                row_color = "#ffdddd"  # Light red for full-day events
                                time_str = "All day"
                                event_type = "Full-day event"
                            else:
                                time_str = f"{event['start']} to {event['end']}"
                                event_type = "Timed event"
                                
                            event_table += f"""
                            <tr style="background-color: {row_color};">
                                <td style="padding: 8px; text-align: left; border: 1px solid #ddd;">{event['title']}</td>
                                <td style="padding: 8px; text-align: left; border: 1px solid #ddd;">{time_str}</td>
                                <td style="padding: 8px; text-align: left; border: 1px solid #ddd;">{event_type}</td>
                            </tr>
                            """
                            
                        event_table += "</table>"
                        st.markdown(event_table, unsafe_allow_html=True)
                        
                        # Highlight if this is the chosen meeting date
                        if formatted_date == report.get("meeting_date"):
                            if any(event["is_full_day"] for event in events):
                                st.warning("This date has full-day events that may conflict with your meeting.")
                            else:
                                st.success("Meeting scheduled on this day in a free time slot between the events above.")
                    else:
                        st.markdown(f"No events found in your calendar for {formatted_date}.")
                        if formatted_date == report.get("meeting_date"):
                            st.success("Meeting scheduled on this day as your calendar was completely free.")
            
            # Overall explanation
            selected_date = report.get("meeting_date", "")
            if selected_date:
                st.info(f"Based on this calendar analysis, the agent selected **{selected_date}** for your meeting.")
        
        # Legacy display based on busy slots
        elif "all_checked_dates" in report and report["all_checked_dates"]:
            st.subheader("Calendar Availability Analysis")
            
            st.markdown("""
            The agent checked your Google Calendar availability for the next few days to find the best meeting time.
            Below are all the dates that were analyzed, with your busy time slots shown for each day.
            """)
            
            # Create tabs for each checked date
            date_tabs = st.tabs([date_info["formatted_date"] for date_str, date_info in sorted(report["all_checked_dates"].items())])
            
            for i, (date_str, date_info) in enumerate(sorted(report["all_checked_dates"].items())):
                with date_tabs[i]:
                    formatted_date = date_info["formatted_date"]
                    busy_slots = date_info["busy_slots"]
                    
                    if busy_slots:
                        st.markdown(f"**Busy time slots on {formatted_date}:**")
                        for j, slot in enumerate(busy_slots, 1):
                            st.markdown(f"**Event {j}:** {slot['start']} to {slot['end']}")
                        
                        # Highlight if this is the chosen meeting date
                        if formatted_date == report.get("meeting_date"):
                            st.success("Meeting scheduled on this day in a free time slot that avoids the conflicts above.")
                    else:
                        st.markdown(f"No events found in your calendar for {formatted_date}.")
                        if formatted_date == report.get("meeting_date"):
                            st.success("Meeting scheduled on this day as your calendar was completely free.")
            
            # Overall explanation
            selected_date = report.get("meeting_date", "")
            if selected_date:
                st.info(f"Based on this analysis, the agent selected **{selected_date}** as the best day for your meeting.")
        
        # Extremely basic legacy display
        elif "busy_slots" in report and report["busy_slots"]:
            st.subheader("Busy Calendar Events")
            st.markdown(f"These are the busy events found in the calendar for **{report.get('meeting_date', 'the requested day')}**:")
            
            for i, slot in enumerate(report["busy_slots"], 1):
                st.markdown(f"**Event {i}:** {slot['start']} to {slot['end']}")
            
            st.info("The agent scheduled your meeting in a free time slot avoiding these busy periods.")
        elif "busy_slots" in report:
            st.markdown("No conflicting events were found in your calendar for the requested date.")
else:
    st.warning("Please enter a lead email to run the workflow.")
