"""Interface for reviewing requirements and tracking editing progress."""

import streamlit as st

from client_requirements import (
    checklist_json,
    document_id,
    extract_requirements,
)


def show_requirements(client, pdf_loader):
    with st.expander("Client requirements", expanded=True):
        st.caption(
            "Upload a client brief or transcript PDF. Extract a draft "
            "checklist, then check each item against its evidence."
        )

        uploaded = st.file_uploader(
            "Client brief PDF",
            type=["pdf"],
            key="requirements_pdf",
        )

        if uploaded is None:
            return

        content = uploaded.getvalue()

        if len(content) > 20 * 1024 * 1024:
            st.error("Use a PDF smaller than 20 MB.")
            return

        identifier = document_id(content)

        checklists = st.session_state.setdefault(
            "client_checklists", {}
        )
        record = checklists.get(identifier)

        if record is None:
            st.caption(
                "Extraction sends this PDF's text to Claude and uses "
                "API credits. Other uploaded documents are not searched."
            )

            if st.button(
                "Extract requirements",
                key=f"extract_{identifier}",
            ):
                try:
                    with st.spinner(
                        "Reading PDF and extracting requirements..."
                    ):
                        documents = pdf_loader(content)
                        pages = [
                            doc.page_content for doc in documents
                        ]

                        rows = extract_requirements(
                            client,
                            pages,
                            uploaded.name,
                        )

                    checklists[identifier] = {
                        "source": uploaded.name,
                        "rows": rows,
                    }

                except Exception as error:
                    st.error(
                        f"Could not extract requirements: {error}"
                    )
                    return

                st.rerun()

            return

        # Restore the latest edits when switching back to this PDF.
        if st.session_state.get("active_checklist") != identifier:
            record["rows"] = record.get("latest", record["rows"])
            record["version"] = record.get("version", 0) + 1
            st.session_state.active_checklist = identifier

        rows = record["rows"]

        st.caption(
            f"Source: {record['source']}. Pages start at 1. "
            "Checklists last for this session; download a copy "
            "to keep them."
        )

        if not rows:
            st.info(
                "No explicit requirements were found. Review the PDF "
                "yourself; extraction can miss items."
            )
            return

        st.info(
            "Draft items can be missed or misinterpreted. Read each "
            "evidence quote, edit the requirement if needed, then "
            "mark Reviewed. Done tracks your own progress."
        )

        edited = st.data_editor(
            rows,
            hide_index=True,
            num_rows="fixed",
            disabled=["Source", "Page", "Evidence"],
            column_config={
                "Requirement": st.column_config.TextColumn(
                    "Requirement",
                    required=True,
                ),
                "Reviewed": st.column_config.CheckboxColumn(
                    "Reviewed"
                ),
                "Done": st.column_config.CheckboxColumn("Done"),
            },
            key=(
                f"checklist_{identifier}_"
                f"{record.get('version', 0)}"
            ),
        )

        record["latest"] = edited

        reviewed = sum(
            bool(row["Reviewed"]) for row in edited
        )

        done = sum(
            bool(row["Done"]) and bool(row["Reviewed"])
            for row in edited
        )

        st.write(
            f"Reviewed: {reviewed}/{len(edited)} | "
            f"Done and reviewed: {done}/{len(edited)}"
        )

        if any(
            row["Done"] and not row["Reviewed"]
            for row in edited
        ):
            st.warning(
                "Review the evidence for items marked Done. "
                "Unreviewed items are not counted as complete."
            )

        st.download_button(
            "Download requirements checklist",
            data=checklist_json(record["source"], edited),
            file_name="client_requirements.json",
            mime="application/json",
            key=f"download_requirements_{identifier}",
        )