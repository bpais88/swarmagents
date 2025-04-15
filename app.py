
import streamlit as st
from orchestrator.graph import run_graph

st.set_page_config(page_title="Swarm Agents Demo", layout="centered")
st.title("Lindy-style Swarm of Agents")

st.markdown("""
Trigger the AI agent workflow to process a mock lead email, schedule a meeting, and log it into CRM.
""")

if st.button("Run Agent Workflow"):
    with st.spinner("Running agents..."):
        report = run_graph()
    st.success("Workflow completed!")

    st.subheader("Agent Thoughts")
    for thought in report["thoughts"]:
        st.markdown(f"- {thought}")

    st.subheader("Tools Used")
    for tool in report["tools_used"]:
        st.code(tool)

    st.subheader("Total Tokens Used")
    st.metric(label="Tokens", value=report["tokens"])
