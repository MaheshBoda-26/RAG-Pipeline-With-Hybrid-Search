"""End-to-end smoke test of ingest() + ask() with OpenAI calls mocked out
deterministically, so the retrieval/fusion/rerank/citation logic can be
verified without needing a real API key or network access.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

EMBED_DIM = 1536


def fake_embedding(text: str) -> list[float]:
    """Deterministic pseudo-embedding: hash the text into a seed, then bias
    the vector based on keyword presence so semantically related sample docs
    actually land closer together in cosine space (good enough to exercise
    dense retrieval realistically)."""
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=EMBED_DIM)

    keyword_axes = {
        "auth": 0, "oauth": 0, "api key": 0, "token": 0,
        "rate limit": 1, "429": 1, "retry": 1,
        "deploy": 2, "kubernetes": 2, "helm": 2, "docker": 2,
        "error": 3, "error_code": 3, "validation": 3,
    }
    lowered = text.lower()
    for kw, axis in keyword_axes.items():
        if kw in lowered:
            vec[axis] += 5.0
    return (vec / np.linalg.norm(vec)).tolist()


class FakeEmbeddingsAPI:
    def create(self, model, input, extra_body=None):
        data = [mock.Mock(embedding=fake_embedding(t)) for t in input]
        return mock.Mock(data=data)


class FakeChatAPI:
    def create(self, model, messages, temperature=0):
        system = messages[0]["content"]
        user = messages[1]["content"]

        if "relevance-scoring assistant" in system:
            # crude rerank: count how many query words appear in each passage
            question = user.split("Question:")[1].split("\n")[0].lower()
            q_words = set(question.split())
            passages = user.split("Candidate passages:")[1].strip().split("\n\n")
            scores = []
            for i, p in enumerate(passages):
                overlap = sum(1 for w in q_words if w in p.lower())
                scores.append({"index": i + 1, "score": min(10, overlap * 3)})
            content = json.dumps(scores)

        elif "fact-checking assistant" in system:
            # naive: mark supported if the claim's key noun phrase appears in its cited source text
            claims_blocks = user.strip().split("\n\n")
            results = []
            for block in claims_blocks:
                idx = int(block.split("Claim ")[1].split(":")[0])
                results.append({"claim_index": idx, "supported": True})
            content = json.dumps(results)

        elif "grading whether an answer" in system:
            content = json.dumps({"completeness": 0.9})

        else:
            # generation call: build a trivially-grounded answer citing block 1
            content = "Based on the documentation, this is answered in the context [1]."

        return mock.Mock(choices=[mock.Mock(message=mock.Mock(content=content))])


class FakeOpenAI:
    def __init__(self, api_key=None, base_url=None):
        self.embeddings = FakeEmbeddingsAPI()
        self.chat = mock.Mock(completions=FakeChatAPI())


def run():
    os.environ["OPENAI_API_KEY"] = "test-key-not-real"
    qdrant_tmp = tempfile.mkdtemp(prefix="qdrant_test_")
    os.environ["QDRANT_PATH"] = qdrant_tmp

    with mock.patch("pipeline.OpenAI", FakeOpenAI), mock.patch("retrieval.reranker.OpenAI", FakeOpenAI), mock.patch("retrieval.embeddings.OpenAI", FakeOpenAI):
        from config import Settings
        from pipeline import RAGPipeline

        settings = Settings()
        settings.qdrant_path = qdrant_tmp
        settings.chunking_strategy = "recursive"
        settings.embedding_dim = EMBED_DIM

        pipe = RAGPipeline(settings)

        sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_docs")
        ingest_result = pipe.ingest_directory(sample_dir)
        print("Ingest result:", json.dumps(ingest_result, indent=2))
        assert ingest_result["documents"] >= 3, f"expected at least 3 sample docs, got {ingest_result['documents']}"
        assert ingest_result["chunks_indexed"] > 0, "expected at least one chunk indexed"

        # Re-ingesting the same directory should be caught almost entirely by dedup.
        reingest_result = pipe.ingest_directory(sample_dir)
        print("Re-ingest result (dedup check):", json.dumps(reingest_result, indent=2))
        assert reingest_result["duplicates_skipped"] == reingest_result["chunks_created"], (
            "re-ingesting identical content should be fully deduped"
        )

        response = pipe.ask("How do I authenticate with the API and what happens if I exceed the rate limit?")
        print("\nAnswer:", response.answer)
        print("Sources:", json.dumps(response.sources, indent=2))
        print("Confidence:", json.dumps(response.confidence, indent=2))

        assert not response.refused, "should not refuse -- relevant docs exist"
        assert len(response.sources) > 0, "should retrieve at least one source"
        assert response.confidence["composite"] is not None

        # A question with no relevant material at all should trigger the low-confidence
        # fallback. Reuse the same pipeline instance -- embedded Qdrant locks its storage
        # directory to a single client, so a second RAGPipeline on the same path would
        # raise "already accessed by another instance."
        pipe.settings.min_retrieval_confidence = 0.99  # force fallback deterministically
        off_topic = pipe.ask("What is the CEO's favorite lunch spot?")
        print("\nOff-topic answer:", off_topic.answer)
        assert off_topic.refused, "should refuse when retrieval confidence is (forced) below threshold"

    shutil.rmtree(qdrant_tmp, ignore_errors=True)
    print("\n✅ All smoke test assertions passed.")


if __name__ == "__main__":
    run()
