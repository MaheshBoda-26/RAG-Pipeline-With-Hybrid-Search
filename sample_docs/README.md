# Demo corpus

Nine short documents on retrieval-augmented generation and adjacent ML topics.
They exist so a fresh clone can run the full pipeline end to end with no setup:

```bash
python cli.py ingest ./sample_docs
python cli.py ask "What does the RAG pipeline combine?"
```

Runtime uploads **never** belong in this repository. The API writes user files
to `sample_docs/<user_id>/uploads/`, which is gitignored — personal documents
must not be committed (this repository's history was scrubbed once already for
exactly that reason, see `docs/TOPTIER_ROADMAP.md`, Phase 0).
