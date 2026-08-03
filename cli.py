"""Usage:
    python cli.py ingest ./sample_docs
    python cli.py ask "How do I authenticate with the API?"
"""
from __future__ import annotations

import argparse
import json
import sys

from config import settings
from pipeline import RAGPipeline


def main():
    parser = argparse.ArgumentParser(description="RAG pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Ingest a directory of documents")
    ingest_p.add_argument("path")

    ask_p = sub.add_parser("ask", help="Ask a question against indexed docs")
    ask_p.add_argument("question")

    args = parser.parse_args()
    pipeline = RAGPipeline(settings)

    if args.command == "ingest":
        result = pipeline.ingest_directory(args.path)
        print(json.dumps(result, indent=2))
    elif args.command == "ask":
        response = pipeline.ask(args.question)
        print(f"\nQ: {response.question}\n")
        print(f"A: {response.answer}\n")
        print("Sources:")
        for s in response.sources:
            print(f"  [{s['block']}] {s['source']}" + (f" ({s['section_heading']})" if s.get("section_heading") else ""))
        print(f"\nConfidence: {json.dumps(response.confidence, indent=2)}")
        if response.refused:
            print(f"\n(refused to answer: {response.refusal_reason})")


if __name__ == "__main__":
    sys.exit(main())
