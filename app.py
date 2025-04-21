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

# 🔐 OAuth credentials from .env
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
SCOPE = "https://www.googleapis.com/auth/calendar"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# 🚧 Sanity check logging
logging.info(f"Client ID: {CLIENT_ID}")
logging.info(f"Redirect URI: {REDIRECT_URI}")

# Step 1: Construct OAuth URL
def get_auth_url():
    params = urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
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
    st.success("✅ Google Calendar is connected!")
    st.info("You can now use the agent workflow below.")
elif not code:
    st.markdown("### Connect your Google Calendar")
    auth_link = get_auth_url()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.link_button("🔐 Authorize Google Calendar", auth_link)
    with col2:
        reset_url = f"{REDIRECT_URI}?reset=true"
        st.link_button("🔄 Reset Auth", reset_url)
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
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    # Add headers for token request
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logging.info(f"Token exchange data: client_id={CLIENT_ID[:8]}..., redirect_uri={REDIRECT_URI}")

    try:
        # Make token exchange request with proper headers
        token_response = requests.post(TOKEN_URL, data=token_data, headers=headers)
        
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

if st.button("🚀 Run Agent Workflow") and lead_text:
    with st.spinner("Running agents..."):
        report = run_graph(email_body=lead_text, lead_rule=lead_rule, access_token=st.session_state.access_token)

    st.success("Workflow completed!")

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
        st.subheader("📅 Meeting Confirmation")
        st.markdown(report["meeting"])
else:
    st.warning("Please enter a lead email to run the workflow.")
