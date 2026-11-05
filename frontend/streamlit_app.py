import os
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 180

st.set_page_config(page_title="Enterprise RAG Intelligence", page_icon="🧠", layout="wide")
st.title("🧠 Enterprise RAG Intelligence Platform")
st.caption("Upload internal knowledge documents and ask grounded questions with source citations.")

def api_request(method: str, path: str, **kwargs):
    try:
        response = requests.request(method, f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        st.error(f"API error: {detail}")
    except requests.RequestException as exc:
        st.error(f"Cannot reach the API at {API_BASE_URL}: {exc}")
    return None


upload_tab, documents_tab, chat_tab = st.tabs(["📤 Upload documents", "📚 Document management", "💬 Knowledge assistant"])

with upload_tab:
    st.subheader("Add knowledge sources")
    uploaded = st.file_uploader("Choose a PDF, TXT or Markdown file", type=["pdf", "txt", "md"])
    if uploaded and st.button("Upload and process", type="primary"):
        with st.spinner("Extracting, chunking and embedding document..."):
            result = api_request(
                "POST",
                "/api/v1/documents/upload",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")},
            )
        if result:
            st.success(result.get("message", "Upload completed."))
            st.json(result.get("document", {}))

with documents_tab:
    st.subheader("Indexed documents")
    if st.button("Refresh document list"):
        st.session_state["refresh_documents"] = True
    if st.session_state.get("refresh_documents", True):
        result = api_request("GET", "/api/v1/documents")
        if result:
            docs = result.get("documents", [])
            if not docs:
                st.info("No documents have been uploaded yet.")
            for doc in docs:
                left, right = st.columns([5, 1])
                with left:
                    st.markdown(f"**{doc['filename']}**")
                    st.caption(f"Status: {doc['status']} · Type: {doc['file_type']} · ID: {doc['id']}")
                with right:
                    if st.button("Delete", key=f"delete_{doc['id']}"):
                        deleted = api_request("DELETE", f"/api/v1/documents/{doc['id']}")
                        if deleted:
                            st.success("Document deleted.")
                            st.rerun()

with chat_tab:
    st.subheader("Ask your documents")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("citations"):
                with st.expander("Sources and retrieved passages"):
                    for citation in message["citations"]:
                        st.markdown(
                            f"**[{citation['source_id']}] {citation['filename']}** — "
                            f"page {citation['page_number']}"
                        )
                        st.caption("Retrieved using: " + ", ".join(citation.get("retrieval_methods", [])))
    question = st.chat_input("Ask a question about your uploaded documents...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching documents and generating an answer..."):
                result = api_request("POST", "/api/v1/chat", json={"question": question})
            if result:
                st.markdown(result["answer"])
                citations = result.get("citations", [])
                if citations:
                    with st.expander("Sources and retrieved passages", expanded=True):
                        for citation in citations:
                            st.markdown(
                                f"**[{citation['source_id']}] {citation['filename']}** — "
                                f"page {citation['page_number']}"
                            )
                            st.caption("Retrieved using: " + ", ".join(citation.get("retrieval_methods", [])))
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "citations": citations,
                })
            else:
                st.warning("The assistant could not complete this request. Check the API logs and configuration.")
