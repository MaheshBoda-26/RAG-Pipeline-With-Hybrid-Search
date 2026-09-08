"""Streamlit-based NotebookLM query dashboard for the RAG pipeline.

Run with: streamlit run dashboard/app.py
"""
import streamlit as st
import requests
import json
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd


# Page config
st.set_page_config(
    page_title="NotebookLM - RAG Pipeline Studio",
    page_icon="📓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for NotebookLM aesthetic
st.markdown("""
<style>
    .stMetric {
        background-color: #f8f9fa;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    .notebook-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .citation-block {
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 12px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.92em;
    }
    .confidence-high { color: #16a34a; font-weight: 600; }
    .confidence-medium { color: #d97706; font-weight: 600; }
    .confidence-low { color: #dc2626; font-weight: 600; }
    .refused-answer {
        background-color: #fff7ed;
        border: 1px solid #fed7aa;
        padding: 16px;
        border-radius: 8px;
        color: #9a3412;
    }
    .source-tag {
        display: inline-block;
        background-color: #eff6ff;
        color: #1d4ed8;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.82em;
        font-weight: 500;
        margin: 2px 4px 2px 0;
        border: 1px solid #dbeafe;
    }
    .chip-btn {
        margin-right: 8px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# Configuration defaults
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_API_KEY = "dev-secret-key"


def init_session_state():
    """Initialize session state variables."""
    if "api_url" not in st.session_state:
        st.session_state.api_url = DEFAULT_API_URL
    if "api_key" not in st.session_state:
        st.session_state.api_key = DEFAULT_API_KEY
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "sparse_weight" not in st.session_state:
        st.session_state.sparse_weight = 0.3
    if "selected_source" not in st.session_state:
        st.session_state.selected_source = "📚 All Documents"
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None
    if "last_upload_info" not in st.session_state:
        st.session_state.last_upload_info = None


def make_request(endpoint: str, payload: Dict, method: str = "POST") -> Dict[str, Any]:
    """Make HTTP JSON request to the API."""
    url = f"{st.session_state.api_url.rstrip('/')}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {st.session_state.api_key}",
    }
    try:
        if method == "POST":
            response = requests.post(url, headers=headers, json=payload, timeout=60)
        else:
            response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def upload_file_to_api(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Upload a file as multipart/form-data to /v1/upload."""
    url = f"{st.session_state.api_url.rstrip('/')}/v1/upload"
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
    }
    files = {
        "file": (filename, file_bytes)
    }
    try:
        response = requests.post(url, headers=headers, files=files, timeout=90)
        if not response.ok:
            try:
                err_detail = response.json().get("detail", response.text)
            except Exception:
                err_detail = response.text
            return {"error": f"Upload failed ({response.status_code}): {err_detail}"}
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Connection error during upload: {str(e)}"}


def delete_document_api(source: str) -> Dict[str, Any]:
    """Delete all chunks for a document from /v1/documents/{source}."""
    url = f"{st.session_state.api_url.rstrip('/')}/v1/documents/{requests.utils.quote(source, safe='')}"
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
    }
    try:
        response = requests.delete(url, headers=headers, timeout=30)
        if not response.ok:
            try:
                err_detail = response.json().get("detail", response.text)
            except Exception:
                err_detail = response.text
            return {"error": f"Delete failed ({response.status_code}): {err_detail}"}
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Connection error: {str(e)}"}


def get_documents_api() -> Dict[str, Any]:
    """Fetch all indexed documents and summary counts from /v1/documents."""
    return make_request("/v1/documents", {}, method="GET")


def render_confidence_badge(confidence: Dict) -> None:
    """Render confidence metrics with NotebookLM-style color coding."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        val = confidence.get("retrieval_confidence") or 0.0
        color = "confidence-high" if val >= 0.7 else "confidence-medium" if val >= 0.4 else "confidence-low"
        st.markdown(f'<div class="stMetric">Retrieval Confidence<br><span class="{color}">{val:.2f}</span></div>', unsafe_allow_html=True)

    with col2:
        val = confidence.get("citation_coverage") or 0.0
        color = "confidence-high" if val >= 0.9 else "confidence-medium" if val >= 0.7 else "confidence-low"
        st.markdown(f'<div class="stMetric">Citation Coverage<br><span class="{color}">{val:.2f}</span></div>', unsafe_allow_html=True)

    with col3:
        val = confidence.get("completeness") or 0.0
        color = "confidence-high" if val >= 0.8 else "confidence-medium" if val >= 0.6 else "confidence-low"
        st.markdown(f'<div class="stMetric">Answer Completeness<br><span class="{color}">{val:.2f}</span></div>', unsafe_allow_html=True)

    with col4:
        val = confidence.get("composite") or 0.0
        color = "confidence-high" if val >= 0.8 else "confidence-medium" if val >= 0.6 else "confidence-low"
        st.markdown(f'<div class="stMetric">Composite Quality<br><span class="{color}">{val:.2f}</span></div>', unsafe_allow_html=True)


def render_sources(sources: List[Dict]) -> None:
    """Render grounded source citations with excerpts and relevance scores."""
    if not sources:
        return

    st.markdown("#### 📖 Grounded Source Citations")
    for source in sources:
        heading = f" ({source['section_heading']})" if source.get('section_heading') else ""
        source_name = source.get('source', 'Unknown')
        block_num = source.get('block', 1)
        
        with st.expander(f"[{block_num}] {source_name}{heading}", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                if source.get('fused_score') is not None:
                    st.caption(f"**RRF Rank Score:** `{source['fused_score']:.4f}`")
            with col2:
                if source.get('rerank_score') is not None:
                    st.caption(f"**Cross-Encoder Rerank:** `{source['rerank_score']:.1f}/10`")
            
            excerpt = source.get("text", "")
            if excerpt:
                st.markdown(f'<div class="citation-block">{excerpt}</div>', unsafe_allow_html=True)


def render_answer_block(response: Dict) -> None:
    """Render the generated answer, confidence scores, and source citations."""
    if response.get("refused"):
        st.markdown(f"""
        <div class="refused-answer">
            <h4>⚠️ Answer Refused</h4>
            <p><strong>Reason:</strong> {response.get('refusal_reason', 'Low retrieval confidence')}</p>
            <p>{response.get('answer', '')}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(response.get("answer", "No answer provided."))

        if response.get("confidence"):
            st.markdown("##### Verification Metrics")
            render_confidence_badge(response["confidence"])

    if response.get("sources"):
        render_sources(response["sources"])


def sidebar_config():
    """Render sidebar configuration and retrieval parameters."""
    with st.sidebar:
        st.title("⚙️ RAG Studio Settings")

        # API Settings
        with st.expander("API Connection", expanded=True):
            st.session_state.api_url = st.text_input(
                "API Base URL",
                value=st.session_state.api_url,
                help="Base URL of the RAG FastAPI service"
            )
            st.session_state.api_key = st.text_input(
                "API Key",
                value=st.session_state.api_key,
                type="password",
                help="Bearer token or user API key"
            )

            if st.button("Test Connection", use_container_width=True):
                result = get_documents_api()
                if "error" in result:
                    st.error(f"Connection failed: {result['error']}")
                else:
                    st.success(f"Connected! {result.get('total_documents', 0)} documents, {result.get('total_chunks', 0)} chunks")

        # Retrieval Settings
        with st.expander("Hybrid Retrieval Parameters", expanded=False):
            dense_weight = st.slider(
                "Dense Weight (Vector / Qdrant)",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.1
            )
            sparse_weight = st.slider(
                "Sparse Weight (Keyword / BM25)",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.1
            )
            total = dense_weight + sparse_weight
            if total > 0:
                dense_weight = dense_weight / total
                sparse_weight = sparse_weight / total
            st.session_state.sparse_weight = sparse_weight
            st.caption(f"Normalized: Dense {dense_weight:.1f} / Sparse {sparse_weight:.1f}")

        st.markdown("---")
        if st.button("Clear Chat History", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()


def run_query(question: str, target_source: Optional[str] = None):
    """Execute a query against the RAG pipeline and record the turn in chat history."""
    source_payload = None if (not target_source or target_source == "📚 All Documents") else target_source

    with st.spinner("Searching sources and synthesizing grounded answer..."):
        start_time = time.time()
        payload = {"question": question}
        if source_payload:
            payload["source"] = source_payload

        response = make_request("/v1/ask", payload, method="POST")
        elapsed = time.time() - start_time

    if "error" in response:
        st.error(f"Error querying pipeline: {response['error']}")
    else:
        st.session_state.chat_history.append({
            "question": question,
            "source": target_source or "📚 All Documents",
            "response": response,
            "time": elapsed,
            "timestamp": time.strftime("%H:%M:%S")
        })


def render_upload_tab():
    """Render the file upload and document sources management tab."""
    st.header("📤 Upload & Document Sources")
    st.markdown("Add new documents to your notebook knowledge base. Files are automatically chunked, embedded, and indexed for hybrid search.")

    # Multi-file uploader
    uploaded_files = st.file_uploader(
        "Choose PDF, DOCX, DOC, TXT, or MD files",
        type=["pdf", "docx", "doc", "txt", "md"],
        accept_multiple_files=True,
        help="Maximum file size 10MB per document."
    )

    if uploaded_files:
        st.markdown(f"**{len(uploaded_files)} file(s) selected.**")
        
        if st.button("🚀 Upload and Index Documents", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []

            for idx, uploaded_file in enumerate(uploaded_files):
                pct = int(((idx) / len(uploaded_files)) * 100)
                progress_bar.progress(pct)
                status_text.text(f"Processing ({idx + 1}/{len(uploaded_files)}): {uploaded_file.name}...")

                file_bytes = uploaded_file.getvalue()
                start_t = time.time()
                res = upload_file_to_api(uploaded_file.name, file_bytes)
                elapsed = time.time() - start_t

                res["elapsed"] = elapsed
                res["original_name"] = uploaded_file.name
                results.append(res)

            progress_bar.progress(100)
            status_text.text("Ingestion completed!")
            time.sleep(0.5)

            st.markdown("### Upload & Ingestion Results")
            for res in results:
                fname = res.get("original_name")
                if "error" in res:
                    st.error(f"❌ **{fname}**: {res['error']}")
                else:
                    chunks_added = res.get("chunks_indexed", res.get("chunks", 0))
                    st.success(f"✅ **{fname}** indexed successfully! ({chunks_added} chunks, {res['elapsed']:.2f}s)")
                    
                    # Immediate NotebookLM transition button
                    col_act1, col_act2 = st.columns([2, 3])
                    with col_act1:
                        if st.button(f"✨ Search & Chat with {fname}", key=f"chat_{fname}"):
                            st.session_state.selected_source = fname
                            st.session_state.pending_question = f"Give me an executive summary of {fname} and highlight the key findings."
                            st.rerun()

    st.markdown("---")
    st.subheader("📚 Active Document Sources")
    
    col_ref, _ = st.columns([1, 5])
    with col_ref:
        refresh_clicked = st.button("🔄 Refresh List")

    doc_data = get_documents_api()
    if "error" in doc_data:
        st.warning(f"Could not load documents: {doc_data['error']}. Check API connection.")
        return

    docs = doc_data.get("documents", [])
    total_docs = doc_data.get("total_documents", len(docs))
    total_chunks = doc_data.get("total_chunks", sum(d.get("chunk_count", 0) for d in docs if isinstance(d, dict)))

    m1, m2 = st.columns(2)
    m1.metric("Indexed Documents", total_docs)
    m2.metric("Total Chunks Stored", total_chunks)

    if not docs:
        st.info("No documents currently indexed. Upload files above to get started.")
    else:
        for item in docs:
            # Handle both string doc name or dict format from list_documents
            if isinstance(item, dict):
                src_name = item.get("source", "unknown")
                chunk_cnt = item.get("chunk_count", 0)
                char_cnt = item.get("total_chars", 0)
            else:
                src_name = str(item)
                chunk_cnt = "N/A"
                char_cnt = "N/A"

            col_name, col_meta, col_del = st.columns([5, 3, 2])
            with col_name:
                st.markdown(f"📄 **{src_name}**")
            with col_meta:
                st.caption(f"Chunks: `{chunk_cnt}` | Chars: `{char_cnt}`")
            with col_del:
                if st.button("🗑️ Delete", key=f"del_{src_name}"):
                    with st.spinner(f"Deleting {src_name}..."):
                        del_res = delete_document_api(src_name)
                        if "error" in del_res:
                            st.error(del_res["error"])
                        else:
                            st.success(f"Deleted {src_name}")
                            time.sleep(0.5)
                            st.rerun()


def render_chat_tab():
    """Render the NotebookLM-style search, exploration, and conversational chat tab."""
    st.header("💬 NotebookLM Chat & Search")
    st.markdown("Explore and query your indexed documents with grounded citations and confidence scores.")

    # Retrieve current documents list for source selector
    doc_data = get_documents_api()
    available_docs = []
    if "error" not in doc_data:
        raw_docs = doc_data.get("documents", [])
        for d in raw_docs:
            name = d.get("source") if isinstance(d, dict) else str(d)
            if name:
                available_docs.append(name)

    source_options = ["📚 All Documents"] + available_docs

    # NotebookLM Source Scope selector
    col_sel, col_info = st.columns([3, 2])
    with col_sel:
        # If previously selected source is in options, keep it; else default to All Documents
        current_idx = 0
        if st.session_state.selected_source in source_options:
            current_idx = source_options.index(st.session_state.selected_source)

        selected_source = st.selectbox(
            "Search Scope (Grounding Source)",
            options=source_options,
            index=current_idx,
            help="Choose whether to search across the entire notebook or focus strictly on one document."
        )
        st.session_state.selected_source = selected_source

    with col_info:
        if selected_source != "📚 All Documents":
            st.markdown(f'<div style="margin-top: 28px;"><span class="source-tag">🎯 Scoped to: {selected_source}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="margin-top: 28px;"><span class="source-tag">🌐 Synthesizing Across Entire Notebook</span></div>', unsafe_allow_html=True)

    # NotebookLM Starter Question Chips
    st.markdown("##### 💡 Suggested Questions")
    chip_cols = st.columns(4)

    is_doc_scoped = selected_source != "📚 All Documents"
    prompt_1 = f"Summarize the main points and thesis of {selected_source}." if is_doc_scoped else "Summarize the core topics covered across all documents."
    prompt_2 = f"What are the key findings, data, and takeaways in {selected_source}?" if is_doc_scoped else "What are the most critical takeaways across all indexed documents?"
    prompt_3 = f"What requirements, instructions, or rules are outlined in {selected_source}?" if is_doc_scoped else "Find and list any action items or requirements mentioned in the sources."
    prompt_4 = f"What questions does {selected_source} answer?" if is_doc_scoped else "Compare and contrast the main perspectives in the documents."

    with chip_cols[0]:
        if st.button("📝 Executive Summary", use_container_width=True):
            st.session_state.pending_question = prompt_1
    with chip_cols[1]:
        if st.button("🔑 Key Takeaways", use_container_width=True):
            st.session_state.pending_question = prompt_2
    with chip_cols[2]:
        if st.button("📋 Requirements & Rules", use_container_width=True):
            st.session_state.pending_question = prompt_3
    with chip_cols[3]:
        if st.button("❓ Key Questions", use_container_width=True):
            st.session_state.pending_question = prompt_4

    st.markdown("---")

    # Render conversational chat message stream
    for turn in st.session_state.chat_history:
        with st.chat_message("user"):
            st.markdown(turn["question"])
            if turn.get("source") and turn["source"] != "📚 All Documents":
                st.caption(f"🎯 Scope: `{turn['source']}`")

        with st.chat_message("assistant"):
            render_answer_block(turn["response"])
            st.caption(f"⏱️ Generated in {turn.get('time', 0):.2f}s at {turn.get('timestamp', '')}")

    # Check if a starter prompt was clicked
    incoming_query = None
    if st.session_state.pending_question:
        incoming_query = st.session_state.pending_question
        st.session_state.pending_question = None

    # Chat input box
    user_input = st.chat_input("Ask a question about your documents...")
    query_to_run = user_input or incoming_query

    if query_to_run:
        with st.chat_message("user"):
            st.markdown(query_to_run)
            if selected_source != "📚 All Documents":
                st.caption(f"🎯 Scope: `{selected_source}`")

        with st.chat_message("assistant"):
            with st.spinner("Searching and synthesizing grounded response..."):
                start_t = time.time()
                payload = {"question": query_to_run}
                if selected_source != "📚 All Documents":
                    payload["source"] = selected_source

                resp = make_request("/v1/ask", payload, method="POST")
                elapsed = time.time() - start_t

            if "error" in resp:
                st.error(f"Error: {resp['error']}")
            else:
                render_answer_block(resp)
                st.caption(f"⏱️ Generated in {elapsed:.2f}s")
                st.session_state.chat_history.append({
                    "question": query_to_run,
                    "source": selected_source,
                    "response": resp,
                    "time": elapsed,
                    "timestamp": time.strftime("%H:%M:%S")
                })


def main():
    """Main application entry point."""
    init_session_state()
    sidebar_config()

    tab_chat, tab_upload = st.tabs([
        "💬 NotebookLM Chat & Search",
        "📤 Upload & Document Sources"
    ])

    with tab_chat:
        render_chat_tab()

    with tab_upload:
        render_upload_tab()


if __name__ == "__main__":
    main()