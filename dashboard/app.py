"""Streamlit-based query dashboard for the RAG pipeline.

Run with: streamlit run dashboard/app.py
"""
import streamlit as st
import requests
import json
import time
from typing import Dict, Any, List
import pandas as pd


# Page config
st.set_page_config(
    page_title="RAG Pipeline Query Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    .citation-block {
        background-color: #f8f9fa;
        border-left: 3px solid #4CAF50;
        padding: 10px;
        margin: 5px 0;
        border-radius: 0 5px 5px 0;
    }
    .confidence-high { color: #4CAF50; font-weight: bold; }
    .confidence-medium { color: #FF9800; font-weight: bold; }
    .confidence-low { color: #F44336; font-weight: bold; }
    .refused-answer {
        background-color: #fff3e0;
        border: 1px solid #FF9800;
        padding: 15px;
        border-radius: 5px;
    }
    .source-tag {
        display: inline-block;
        background-color: #e3f2fd;
        color: #1565c0;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.85em;
        margin: 2px;
    }
</style>
""", unsafe_allow_html=True)


# Configuration
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_API_KEY = "dev-secret-key"


def init_session_state():
    """Initialize session state variables."""
    if "api_url" not in st.session_state:
        st.session_state.api_url = DEFAULT_API_URL
    if "api_key" not in st.session_state:
        st.session_state.api_key = DEFAULT_API_KEY
    if "history" not in st.session_state:
        st.session_state.history = []
    if "sparse_weight" not in st.session_state:
        st.session_state.sparse_weight = 0.3


def make_request(endpoint: str, payload: Dict, method: str = "POST") -> Dict[str, Any]:
    """Make HTTP request to the API."""
    url = f"{st.session_state.api_url}{endpoint}"
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


def render_confidence_badge(confidence: Dict) -> None:
    """Render confidence metrics with color coding."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        val = confidence.get("retrieval_confidence", 0)
        color = "confidence-high" if val >= 0.7 else "confidence-medium" if val >= 0.4 else "confidence-low"
        st.markdown(f'<div class="stMetric"><span class="{color}">Retrieval: {val:.2f}</span></div>', unsafe_allow_html=True)

    with col2:
        val = confidence.get("citation_coverage", 0)
        color = "confidence-high" if val >= 0.9 else "confidence-medium" if val >= 0.7 else "confidence-low"
        st.markdown(f'<div class="stMetric"><span class="{color}">Citation: {val:.2f}</span></div>', unsafe_allow_html=True)

    with col3:
        val = confidence.get("completeness", 0)
        color = "confidence-high" if val >= 0.8 else "confidence-medium" if val >= 0.6 else "confidence-low"
        st.markdown(f'<div class="stMetric"><span class="{color}">Complete: {val:.2f}</span></div>', unsafe_allow_html=True)

    with col4:
        val = confidence.get("composite", 0)
        color = "confidence-high" if val >= 0.8 else "confidence-medium" if val >= 0.6 else "confidence-low"
        st.markdown(f'<div class="stMetric"><span class="{color}">Composite: {val:.2f}</span></div>', unsafe_allow_html=True)


def render_sources(sources: List[Dict]) -> None:
    """Render source citations."""
    if not sources:
        st.info("No sources retrieved")
        return

    st.subheader("📚 Sources")
    for source in sources:
        with st.expander(f"[{source['block']}] {source['source']}" + (f" ({source['section_heading']})" if source.get('section_heading') else "")):
            col1, col2 = st.columns(2)
            with col1:
                if source.get('fused_score') is not None:
                    st.metric("RRF Score", f"{source['fused_score']:.4f}")
            with col2:
                if source.get('rerank_score') is not None:
                    st.metric("Rerank Score", f"{source['rerank_score']:.1f}/10")


def render_answer(response: Dict) -> None:
    """Render the answer with citations and confidence."""
    if response.get("refused"):
        st.markdown(f"""
        <div class="refused-answer">
            <h4>⚠️ Answer Refused</h4>
            <p><strong>Reason:</strong> {response.get('refusal_reason', 'Unknown')}</p>
            <p>{response.get('answer', '')}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("### Answer")
        st.write(response.get("answer", "No answer"))

        if response.get("confidence"):
            st.markdown("### Confidence Scores")
            render_confidence_badge(response["confidence"])

    if response.get("sources"):
        render_sources(response["sources"])


def sidebar_config():
    """Render sidebar configuration."""
    with st.sidebar:
        st.header("⚙️ Configuration")

        # API Settings
        with st.expander("API Settings", expanded=True):
            st.session_state.api_url = st.text_input(
                "API Base URL",
                value=st.session_state.api_url,
                help="Base URL of the RAG API (e.g., http://localhost:8000)"
            )
            st.session_state.api_key = st.text_input(
                "API Key",
                value=st.session_state.api_key,
                type="password",
                help="Bearer token for authentication"
            )

            if st.button("Test Connection"):
                result = make_request("/v1/documents", {}, method="GET")
                if "error" in result:
                    st.error(f"Connection failed: {result['error']}")
                else:
                    st.success(f"Connected! {result.get('total_chunks', 0)} chunks indexed")

        # Retrieval Settings
        with st.expander("Retrieval Settings", expanded=True):
            st.markdown("**Hybrid Search Weights**")
            st.markdown("*Dense (vector) + Sparse (BM25) = 1.0*")

            dense_weight = st.slider(
                "Dense Weight",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.1,
                help="Weight for dense vector search (Qdrant)"
            )

            sparse_weight = st.slider(
                "Sparse Weight",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.1,
                help="Weight for sparse keyword search (BM25)"
            )

            # Normalize to sum to 1.0
            total = dense_weight + sparse_weight
            if total > 0:
                dense_weight = dense_weight / total
                sparse_weight = sparse_weight / total

            st.session_state.sparse_weight = sparse_weight
            st.info(f"Normalized: Dense={dense_weight:.1f}, Sparse={sparse_weight:.1f}")

            # Quick toggles
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 Hybrid (70/30)"):
                    st.session_state.sparse_weight = 0.3
                    st.rerun()
            with col2:
                if st.button("🎯 Dense Only"):
                    st.session_state.sparse_weight = 0.0
                    st.rerun()

        # Document Management
        with st.expander("📄 Document Management"):
            if st.button("List Documents"):
                result = make_request("/v1/documents", {}, method="GET")
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.write(f"**Documents:** {len(result.get('documents', []))}")
                    st.write(f"**Total Chunks:** {result.get('total_chunks', 0)}")
                    for doc in result.get('documents', []):
                        st.text(doc)

            ingest_path = st.text_input("Ingest Path", value="./sample_docs")
            if st.button("Ingest Documents"):
                with st.spinner("Ingesting..."):
                    result = make_request("/v1/ingest", {"path": ingest_path})
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(f"Ingested: {result.get('documents', 0)} docs, {result.get('chunks_indexed', 0)} chunks")
                        if result.get('duplicates_skipped', 0) > 0:
                            st.info(f"Skipped {result['duplicates_skipped']} duplicates")

        # History
        with st.expander("📜 Query History", expanded=False):
            if st.session_state.history:
                for i, item in enumerate(reversed(st.session_state.history[-10:])):
                    st.text(f"{len(st.session_state.history) - i}. {item['question'][:50]}...")
            else:
                st.text("No queries yet")

            if st.button("Clear History"):
                st.session_state.history = []
                st.rerun()


def main():
    """Main dashboard application."""
    init_session_state()
    sidebar_config()

    # Header
    st.title("🔍 RAG Pipeline Query Dashboard")
    st.markdown("Ask questions against your indexed documentation with hybrid search.")

    # Query input
    col1, col2 = st.columns([5, 1])
    with col1:
        question = st.text_input(
            "Question",
            placeholder="e.g., What is the rate limit for API keys?",
            label_visibility="collapsed"
        )
    with col2:
        ask_button = st.button("Ask", type="primary", use_container_width=True)

    # Process query
    if ask_button and question:
        with st.spinner("Retrieving and generating answer..."):
            start_time = time.time()

            # Note: The current API doesn't support passing sparse_weight per request
            # This would need to be added to the pipeline or config
            response = make_request("/v1/ask", {"question": question})

            elapsed = time.time() - start_time

        if "error" in response:
            st.error(f"Error: {response['error']}")
        else:
            # Add to history
            st.session_state.history.append({
                "question": question,
                "response": response,
                "time": elapsed,
                "timestamp": time.strftime("%H:%M:%S")
            })

            # Render response
            st.markdown("---")
            render_answer(response)

            # Show latency
            st.caption(f"⏱️ Response time: {elapsed:.2f}s")

    # Show history
    if st.session_state.history:
        st.markdown("---")
        st.subheader("📜 Recent Queries")

        for item in reversed(st.session_state.history[-5:]):
            with st.expander(f"{item['timestamp']} - {item['question'][:80]}... ({item['time']:.2f}s)"):
                render_answer(item['response'])


if __name__ == "__main__":
    main()