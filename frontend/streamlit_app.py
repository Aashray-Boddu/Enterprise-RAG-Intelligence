import html
import os
from typing import Any

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 180

st.set_page_config(
    page_title="Enterprise RAG Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
:root {
    --canvas: #F4F2EA;
    --surface: #FFFFFF;
    --surface-soft: #EEF1E9;
    --ink: #24332B;
    --ink-soft: #52645A;
    --muted: #77857B;
    --line: #DCE3D9;
    --forest: #315C46;
    --forest-deep: #244634;
    --sage: #DDE8DE;
    --terracotta: #B86F50;
    --terracotta-soft: #F4E8E1;
}

.stApp {
    background: var(--canvas);
    color: var(--ink);
}

[data-testid="stHeader"] {
    background: rgba(244, 242, 234, 0.88);
}

.block-container {
    max-width: 1280px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}

h1, h2, h3, h4 {
    color: var(--ink) !important;
    letter-spacing: -0.025em;
}

h1 { font-weight: 720 !important; }
h2, h3 { font-weight: 650 !important; }
p, label, li, .stMarkdown { color: var(--ink-soft); }
small, [data-testid="stCaptionContainer"] { color: var(--muted) !important; }

[data-testid="stSidebar"] {
    background: #E9EDE5;
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: var(--ink-soft);
}

.brand-lockup {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 0 0 1.35rem 0;
}
.brand-mark {
    width: 42px;
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    background: var(--forest);
    color: #FFFFFF;
    font-family: Georgia, serif;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -1px;
}
.brand-name {
    color: var(--ink);
    font-size: 15px;
    line-height: 1.15;
    font-weight: 750;
}
.brand-subtitle {
    color: var(--muted);
    font-size: 10px;
    margin-top: 4px;
    letter-spacing: .12em;
    text-transform: uppercase;
}

.hero-panel {
    background: linear-gradient(115deg, #294A38 0%, #365F49 58%, #58755D 100%);
    border-radius: 20px;
    padding: 30px 34px;
    margin: 0 0 1.5rem 0;
    color: #F8F7F1;
    box-shadow: 0 12px 28px rgba(38, 63, 47, .11);
}
.hero-kicker {
    color: #D9E5D8;
    text-transform: uppercase;
    letter-spacing: .16em;
    font-size: 10px;
    font-weight: 700;
    margin-bottom: 11px;
}
.hero-title {
    color: #FFFFFF;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(27px, 3.1vw, 39px);
    font-weight: 600;
    letter-spacing: -.035em;
    line-height: 1.12;
    margin: 0;
}
.hero-copy {
    color: #E4EBE1;
    max-width: 760px;
    font-size: 14px;
    line-height: 1.65;
    margin-top: 12px;
}
.hero-tag {
    display: inline-block;
    margin-top: 17px;
    border: 1px solid rgba(255,255,255,.28);
    border-radius: 999px;
    padding: 5px 11px;
    color: #F6F6EF;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: .1em;
}

.section-eyebrow {
    color: var(--terracotta);
    font-size: 10px;
    font-weight: 750;
    letter-spacing: .15em;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.section-intro {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.55;
    margin: 0 0 1.1rem 0;
}

[data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent;
    border-bottom: 1px solid var(--line);
}
[data-baseweb="tab"] {
    background: transparent;
    color: var(--muted);
    border-radius: 9px 9px 0 0;
    padding: 10px 17px;
    font-weight: 600;
}
[data-baseweb="tab"][aria-selected="true"] {
    color: var(--forest-deep);
    border-bottom: 3px solid var(--forest);
}

.stButton > button {
    border-radius: 9px;
    border: 1px solid var(--line);
    background: #FFFFFF;
    color: var(--ink);
    font-weight: 650;
    padding: .56rem 1rem;
    transition: all .15s ease;
}
.stButton > button:hover {
    border-color: var(--forest);
    color: var(--forest-deep);
    background: #F7F9F5;
}
.stButton > button[kind="primary"] {
    background: var(--forest);
    border-color: var(--forest);
    color: #FFFFFF;
}
.stButton > button[kind="primary"]:hover {
    background: var(--forest-deep);
    border-color: var(--forest-deep);
    color: #FFFFFF;
}

[data-testid="stFileUploader"] section {
    background: #FBFCF9;
    border: 1px dashed #AAB9AA;
    border-radius: 13px;
}
[data-testid="stFileUploader"] button {
    border-radius: 8px;
}

[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid var(--line);
    border-radius: 13px;
    padding: 14px 16px;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; }
[data-testid="stMetricValue"] { color: var(--forest-deep) !important; }

[data-testid="stExpander"] {
    background: rgba(255,255,255,.72);
    border: 1px solid var(--line);
    border-radius: 12px;
}
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,.72);
    border: 1px solid var(--line);
    border-radius: 15px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
[data-testid="stChatInput"] textarea {
    background: #FFFFFF;
    border: 1px solid #CBD7CA;
    border-radius: 13px;
}

input, textarea, [data-baseweb="select"] > div {
    border-radius: 9px !important;
}
hr { border-color: var(--line); }

.status-pill {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 999px;
    background: var(--sage);
    color: var(--forest-deep);
    font-size: 10px;
    font-weight: 750;
    letter-spacing: .05em;
    text-transform: uppercase;
}
.status-pill-warn {
    background: var(--terracotta-soft);
    color: #895139;
}
.doc-name {
    color: var(--ink);
    font-weight: 700;
    font-size: 14px;
}
.doc-meta {
    color: var(--muted);
    font-size: 11px;
    margin-top: 4px;
    overflow-wrap: anywhere;
}
.source-label {
    color: var(--forest-deep);
    font-weight: 750;
}
.footer-note {
    color: var(--muted);
    font-size: 11px;
    text-align: center;
    padding-top: 1.5rem;
}

@media (max-width: 700px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .hero-panel { padding: 23px 21px; }
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def api_request(method: str, path: str, *, show_error: bool = True, **kwargs: Any) -> dict | None:
    """Call the backend API and show a useful UI-level error when requested."""
    try:
        response = requests.request(
            method,
            f"{API_BASE_URL}{path}",
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()
    except requests.HTTPError as exc:
        try:
            detail = exc.response.json().get("detail", str(exc))
        except (ValueError, AttributeError):
            detail = str(exc)
        if show_error:
            st.error(f"The API returned an error: {detail}")
    except requests.RequestException as exc:
        if show_error:
            st.error(f"Cannot reach the backend at {API_BASE_URL}: {exc}")
    except ValueError as exc:
        if show_error:
            st.error(f"The backend returned an unreadable response: {exc}")
    return None


def render_brand_header() -> None:
    st.markdown(
        """
        <div class="hero-panel">
            <div class="hero-kicker">Knowledge operations · Document intelligence</div>
            <div class="hero-title">Enterprise RAG Intelligence</div>
            <div class="hero-copy">
                A document-grounded workspace for searching internal knowledge,
                reviewing source material, and getting answers with traceable citations.
            </div>
            <span class="hero-tag">Private knowledge · Hybrid retrieval · Source-aware answers</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_citations(citations: list[dict]) -> None:
    if not citations:
        st.caption("No source passages were returned for this answer.")
        return
    with st.expander(f"Evidence and citations · {len(citations)} source passage(s)", expanded=False):
        for citation in citations:
            source_id = citation.get("source_id", "Source")
            filename = citation.get("filename", "Unknown file")
            page_number = citation.get("page_number", "—")
            methods = citation.get("retrieval_methods") or []
            st.markdown(
                f"**[{source_id}] {filename}**  \n"
                f"Page {page_number} · Retrieved by {', '.join(methods) if methods else 'retrieval pipeline'}"
            )
            score = citation.get("retrieval_score")
            if score is not None:
                st.caption(f"RRF score: {float(score):.5f}")


def render_document_card(document: dict) -> None:
    filename = html.escape(str(document.get("filename", "Unnamed document")))
    file_type = str(document.get("file_type", "unknown")).upper()
    status = str(document.get("status", "unknown")).lower()
    created_at = document.get("created_at") or "Date unavailable"
    document_id = html.escape(str(document.get("id", "")))

    with st.container(border=True):
        left, middle, right = st.columns([5, 1.4, 1.1], vertical_alignment="center")
        with left:
            st.markdown(f'<div class="doc-name">{filename}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="doc-meta">{file_type} · Added {created_at}<br>ID: {document_id}</div>',
                unsafe_allow_html=True,
            )
        with middle:
            pill_class = "status-pill" if status == "ready" else "status-pill status-pill-warn"
            st.markdown(
                f'<span class="{pill_class}">{status}</span>',
                unsafe_allow_html=True,
            )
        with right:
            if st.button("Delete", key=f"delete_{document_id}", use_container_width=True):
                deleted = api_request("DELETE", f"/api/v1/documents/{document_id}")
                if deleted is not None:
                    st.toast(f"Removed {filename}", icon="✓")
                    st.rerun()


# Sidebar: product identity and backend connectivity.
with st.sidebar:
    st.markdown(
        """
        <div class="brand-lockup">
            <div class="brand-mark">ER</div>
            <div>
                <div class="brand-name">Enterprise RAG</div>
                <div class="brand-subtitle">Intelligence workspace</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("**Workspace**")
    st.caption("Manage source documents and ask questions grounded in indexed content.")
    st.divider()
    st.markdown("**Backend connection**")
    st.caption(API_BASE_URL)
    health = api_request("GET", "/health", show_error=False)
    if health and health.get("status") == "ok":
        st.success("API and database connected")
    elif health:
        st.warning(f"Backend status: {health.get('status', 'unknown')} · DB: {health.get('database', 'unknown')}")
    else:
        st.error("Backend unavailable")
    if st.button("Recheck connection", use_container_width=True):
        st.rerun()
    st.divider()
    st.markdown("**Supported sources**")
    st.caption("PDF · TXT · Markdown")
    st.caption("Maximum upload size: 25 MB per file")
    st.markdown("<div class='footer-note'>Local development workspace</div>", unsafe_allow_html=True)


render_brand_header()

upload_tab, library_tab, assistant_tab = st.tabs(
    ["Document intake", "Knowledge library", "Research assistant"]
)

with upload_tab:
    st.markdown('<div class="section-eyebrow">01 / Ingestion</div>', unsafe_allow_html=True)
    st.subheader("Add a knowledge source")
    st.markdown(
        '<p class="section-intro">Import a PDF, text file, or Markdown document. The backend extracts text, '
        'creates overlapping chunks, generates embeddings, and stores the result for retrieval.</p>',
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Select a document",
        type=["pdf", "txt", "md"],
        help="Supported formats: PDF, TXT and Markdown. Maximum size: 25 MB.",
    )
    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        st.caption(f"Selected: {uploaded_file.name} · {file_size_mb:.2f} MB")

    upload_col, note_col = st.columns([1.15, 2.85], vertical_alignment="center")
    with upload_col:
        upload_clicked = st.button(
            "Process document",
            type="primary",
            disabled=uploaded_file is None,
            use_container_width=True,
        )
    with note_col:
        st.caption("Processing time depends on document length and local embedding-model availability.")

    if upload_clicked and uploaded_file is not None:
        with st.spinner("Extracting text, creating chunks and generating embeddings..."):
            result = api_request(
                "POST",
                "/api/v1/documents/upload",
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type or "application/octet-stream",
                    )
                },
            )
        if result:
            document = result.get("document", {})
            st.success(result.get("message", "Document processed successfully."))
            with st.container(border=True):
                st.markdown("**Ingestion complete**")
                st.write(f"Document: `{document.get('filename', uploaded_file.name)}`")
                st.write(f"Status: `{document.get('status', 'unknown')}`")
                st.caption(f"Document ID: {document.get('id', 'not returned')}")

with library_tab:
    st.markdown('<div class="section-eyebrow">02 / Repository</div>', unsafe_allow_html=True)
    st.subheader("Knowledge library")
    st.markdown(
        '<p class="section-intro">Review indexed documents and remove sources that should no longer '
        'participate in retrieval.</p>',
        unsafe_allow_html=True,
    )

    refresh_col, spacer_col = st.columns([1, 4])
    with refresh_col:
        st.button("Refresh library", use_container_width=True)
    documents_result = api_request("GET", "/api/v1/documents", show_error=False)
    if documents_result is None:
        st.info("The document library is unavailable until the backend is running.")
    else:
        documents = documents_result.get("documents", [])
        ready_count = sum(1 for item in documents if item.get("status") == "ready")
        type_count = len({item.get("file_type") for item in documents})
        metric_a, metric_b, metric_c = st.columns(3)
        metric_a.metric("Indexed documents", len(documents))
        metric_b.metric("Ready for retrieval", ready_count)
        metric_c.metric("File formats", type_count)
        st.write("")
        if not documents:
            st.info("No documents have been indexed yet. Add a source from the Document intake tab.")
        else:
            for document in documents:
                render_document_card(document)

with assistant_tab:
    st.markdown('<div class="section-eyebrow">03 / Knowledge assistant</div>', unsafe_allow_html=True)
    st.subheader("Ask the knowledge base")
    st.markdown(
        '<p class="section-intro">Ask a question in natural language. Answers are generated from retrieved '
        'document passages and should include source references.</p>',
        unsafe_allow_html=True,
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    chat_header_left, chat_header_right = st.columns([4, 1])
    with chat_header_left:
        st.caption("Use specific questions for clearer, easier-to-verify answers.")
    with chat_header_right:
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("citations"):
                render_citations(message["citations"])

    question = st.chat_input("Ask about a policy, process, figure, or requirement...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching indexed sources and preparing an answer..."):
                result = api_request("POST", "/api/v1/chat", json={"question": question})
            if result:
                answer = result.get("answer", "No answer was returned.")
                citations = result.get("citations", [])
                st.markdown(answer)
                render_citations(citations)
                st.caption(f"Retrieved passages: {result.get('retrieved_chunks', 0)}")
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "citations": citations}
                )
            else:
                st.warning("The assistant could not complete this request. Check the backend terminal for details.")

st.markdown(
    '<div class="footer-note">Enterprise RAG Intelligence · Document-grounded answers with source transparency</div>',
    unsafe_allow_html=True,
)
