"""One-off cleanup of the polluted `user_default` Supabase collection.

Deletes:
  1. Scratch/test docs (test*.txt, doc*.txt, question_test.txt, ...)
  2. AI-topic sample docs (ml_intro, neural_networks, gen_ai, nlp_overview,
     computer_vision, data_science, reinforcement_learning, ml_fundamentals,
     rag_overview)
  3. Duplicate resume copies (same content ingested under different filenames;
     keeps the OLDEST original, deletes re-uploads with uuid prefixes)

Usage:
  python scripts/clean_user_default.py           # dry run: shows the plan
  python scripts/clean_user_default.py --apply   # requires typing DELETE

Run with the project venv: .venv/bin/python scripts/clean_user_default.py
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

AI_TOPICS = re.compile(
    r"(ml_intro|neural_networks|gen_ai|nlp_overview|computer_vision|"
    r"data_science|reinforcement_learning|ml_fundamentals|rag_overview)",
    re.I,
)
SCRATCH = re.compile(r"^(test|doc|question_test)\b", re.I)


def classify_source(src: str) -> str:
    """Return 'scratch' | 'ai_topic' | 'dup' | 'keep' for a source path."""
    base = re.sub(r"^[0-9a-f]{8}_", "", src.rsplit("/", 1)[-1], flags=re.I)
    base = re.sub(r"\.(txt|md|docx?)$", "", base, flags=re.I)
    if SCRATCH.match(base):
        return "scratch"
    if AI_TOPICS.search(base):
        return "ai_topic"
    return "keep"


def main() -> None:
    from supabase import create_client

    c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    cid = c.table("collections").select("id").eq("name", "user_default").execute().data[0]["id"]
    rows = (
        c.table("vectors").select("id, payload, created_at")
        .eq("collection_id", cid).limit(1000).execute().data
    )

    delete_ids: list[str] = []
    delete_sources: set[str] = set()
    keep_sources: set[str] = set()

    # --- 1+2: scratch and AI-topic docs ---
    for r in rows:
        src = r["payload"].get("source", "")
        kind = classify_source(src)
        if kind in ("scratch", "ai_topic"):
            delete_ids.append(r["id"])
            delete_sources.add(src)
        else:
            keep_sources.add(src)

    # --- 3: duplicate resume copies ---
    # Group remaining resume chunks by canonical content name; among sources
    # sharing a canonical name, keep the oldest (the original upload), delete
    # the rest (uuid-prefixed re-uploads).
    by_canonical: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for src in keep_sources:
        m = re.search(r"Mahesh_Boda_[^/]*$", src)
        canonical = m.group(0) if m else src.rsplit("/", 1)[-1]
        # fetch oldest created_at for this source from rows
        created = min((r["created_at"] for r in rows if r["payload"].get("source") == src), default="")
        by_canonical[canonical].append((created, src))

    for canonical, entries in by_canonical.items():
        if len(entries) > 1:
            entries.sort()  # oldest first by created_at
            for _, src in entries[1:]:
                for r in rows:
                    if r["payload"].get("source") == src:
                        delete_ids.append(r["id"])
                        delete_sources.add(src)

    keep_count = sum(1 for r in rows if r["id"] not in set(delete_ids))
    print(f"Collection user_default: {len(rows)} chunks total")
    print(f"  KEEP    {keep_count} chunks across {len(keep_sources - delete_sources)} sources")
    print(f"  DELETE  {len(delete_ids)} chunks across {len(delete_sources)} sources:\n")
    for s in sorted(delete_sources):
        print(f"    - {s}")

    if "--apply" not in sys.argv:
        print("\nDRY RUN — rerun with --apply to delete (you must also type DELETE).")
        return

    confirm = input("\nType DELETE to confirm: ").strip()
    if confirm != "DELETE":
        print("Aborted.")
        return

    for i in range(0, len(delete_ids), 100):
        c.table("vectors").delete().in_("id", delete_ids[i : i + 100]).execute()
    print(f"Deleted {len(delete_ids)} chunks across {len(delete_sources)} sources.")

    # Rebuild the BM25 index so it no longer references deleted chunks.
    from config import Settings
    from pipeline import RAGPipeline

    pipe = RAGPipeline(Settings(), user_id="default")
    pipe._rebuild_sparse_index()
    print("BM25 index rebuilt.")


if __name__ == "__main__":
    main()
