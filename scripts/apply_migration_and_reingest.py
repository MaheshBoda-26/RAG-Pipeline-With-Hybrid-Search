"""Apply the 2048-dim migration + re-ingest, in one command.

Tries every known-good Supabase connection path with the password currently in
.env. Exits with a clear message if none authenticate (then the password must
be rotated in Supabase Dashboard -> Settings -> Database, and SUPABASE_DB_URL in
.env updated).

Usage: .venv/bin/python scripts/apply_migration_and_reingest.py [--skip-reingest]
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def connection_candidates() -> list[str]:
    url = os.environ["SUPABASE_DB_URL"]
    m = re.search(r"://([^:]+):([^@]+)@", url)
    pw = m.group(2)
    ref = "lcqtaxwqicmctaamqptj"
    return [
        f"postgresql://postgres:{pw}@db.{ref}.supabase.co:5432/postgres",
        f"postgresql://postgres.{ref}:{pw}@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
        f"postgresql://postgres.{ref}:{pw}@aws-0-us-east-1.pooler.supabase.com:5432/postgres",
    ]


def apply_migration() -> bool:
    import psycopg

    sql = (ROOT / "scripts" / "migrate_vector_dim_2048.sql").read_text()
    for conn_url in connection_candidates():
        try:
            with psycopg.connect(conn_url, autocommit=True, connect_timeout=15) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT atttypmod FROM pg_attribute "
                        "WHERE attrelid='vectors'::regclass AND attname='embedding'"
                    )
                    typmod = cur.fetchone()[0]
                    cur.execute("SELECT proname FROM pg_proc WHERE proname='match_vectors'")
                    has_rpc = bool(cur.fetchone())
            dims = (typmod - 4) // 8 if typmod and typmod > 32 else typmod
            print(f"Migration applied via {conn_url.split('@')[1].split(':')[0]}")
            print(f"  vectors.embedding dims: {dims}")
            print(f"  match_vectors RPC: {'present' if has_rpc else 'MISSING'}")
            return dims == 2048 and has_rpc
        except Exception as e:
            print(f"  conn failed ({str(e)[:80]}...)")
    print(
        "\nALL CONNECTIONS FAILED — the password in SUPABASE_DB_URL is stale.\n"
        "Fix: Supabase Dashboard -> Settings -> Database -> reset database password,\n"
        "then update SUPABASE_DB_URL in .env and rerun this script."
    )
    return False


def reingest() -> None:
    from config import Settings
    from pipeline import RAGPipeline

    pipe = RAGPipeline(Settings(), user_id="default")
    docs = sorted((ROOT / "sample_docs" / "default" / "uploads").glob("*.docx"))
    total = 0
    for d in docs:
        name = d.name
        orig = name.split("_", 1)[1] if re.match(r"^[0-9a-f]{8}_", name) else name
        try:
            r = pipe.ingest_file(str(d), original_filename=orig, user_id="default")
            total += r["chunks_indexed"]
            print(f"  {orig}: indexed={r['chunks_indexed']} dup={r['duplicates_skipped']}")
        except Exception as e:
            print(f"  {orig}: FAILED {str(e)[:120]}")
    print(f"TOTAL chunks indexed: {total}")


if __name__ == "__main__":
    ok = apply_migration()
    if not ok:
        sys.exit(1)
    if "--skip-reingest" not in sys.argv:
        print("\nRe-ingesting real documents with nvidia/nemotron-3-embed-1b (2048d)...")
        reingest()
    print("\nDone. The live demo upload should now work.")
