import streamlit as st
from orchestrator.graph import run_graph
from memory.supabase_memory import memory

st.set_page_config(page_title="Lindy-style Swarm of Agents", layout="centered")
st.title("Lindy-style Swarm of Agents")

st.markdown("""
Trigger the AI agent workflow to process a lead email, schedule a meeting, and log it into CRM.
You can provide the lead email and the rule for how the agent should classify it.
""")

# Dynamic user input
lead_text = st.text_area("Paste Lead Email", height=200)
lead_rule = st.text_input(
    "Lead Qualification Rule",
    value="Consider it a lead if the sender asks for a meeting, demo, or pricing."
)

# Trigger the workflow
if st.button("Run Agent Workflow") and lead_text:
    with st.spinner("Running agents..."):
        report = run_graph(email_body=lead_text, lead_rule=lead_rule)

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
else:
    st.warning("Please enter a lead email to run the workflow.")
