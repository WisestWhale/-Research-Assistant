import streamlit as st


def show_action(action, key, enabled=True):
    st.write("Suggested browser action")
    st.text(action.url)
    st.write(action.reason)
    if action.status == "pending":
        if st.button("Open page", key=f"open_{key}", disabled=not enabled):
            action.open()
            st.rerun()
        if st.button("Cancel", key=f"cancel_{key}"):
            action.cancel()
            st.rerun()
    elif action.status == "opened":
        st.success("Sent to your browser. Check the new tab.")
    elif action.status == "cancelled":
        st.caption("Cancelled.")
    else:
        st.error("Could not launch the browser. You can copy the URL above.")
