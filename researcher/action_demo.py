import streamlit as st
from browser_action import BrowserAction
from action_ui import show_action
from research_tools import Source

st.title("Browser action demo")
st.write("Try the approval step without API keys. Run this app on your own computer.")
if "demo_action" not in st.session_state:
    source = Source("Python documentation", "https://docs.python.org/3/")
    st.session_state.demo_action = BrowserAction.from_sources(
        source.url, "Open the Python documentation in a new tab.", [source]
    )
show_action(st.session_state.demo_action, "demo")
if st.button("Reset demo"):
    del st.session_state.demo_action
    st.rerun()
