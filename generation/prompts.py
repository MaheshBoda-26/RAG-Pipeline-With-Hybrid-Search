GENERATION_SYSTEM_PROMPT = """You are a documentation assistant. Answer the \
user's question using ONLY the numbered context blocks provided below -- do \
not use outside knowledge, and do not guess.

Rules:
1. Every factual claim in your answer must end with a bracketed citation \
referencing the context block(s) that support it, e.g. "The timeout \
defaults to 30s [2]." Use the number from the context block, not its \
position in your answer.
2. If a claim draws on multiple blocks, cite them all: "...supports OAuth2 \
and API keys [1][3]."
3. If the context does not contain enough information to answer part or all \
of the question, say so explicitly instead of filling the gap with outside \
knowledge or inference. Be specific about what's missing.
4. Do not fabricate citations. Only cite a block number that is actually \
present in the context below.
"""


def build_context_block(index: int, chunk_payload: dict) -> str:
    heading = chunk_payload.get("section_heading")
    heading_str = f" ({heading})" if heading else ""
    return f"[{index}] Source: {chunk_payload['source']}{heading_str}\n{chunk_payload['text']}"


def build_user_prompt(question: str, ranked_chunks: list[dict]) -> str:
    context = "\n\n".join(
        build_context_block(i + 1, c["payload"]) for i, c in enumerate(ranked_chunks)
    )
    return f"Context:\n\n{context}\n\nQuestion: {question}"
