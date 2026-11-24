# AGENTS.md — Plan Mode (Architecture / Design)

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Architectural Constraints

- **Ports are `typing.Protocol`** (structural), not ABC — this means the type checker enforces the interface but there is no runtime enforcement. Any class matching the protocol's shape is valid, without registering anywhere.
- **RAG index dimension is set at build time** (`EMBEDDING_DIMENSION` env var) and validated against `manifest.json` on every startup. Changing embedding providers requires rebuilding the index (`make index`) AND updating `EMBEDDING_DIMENSION`; mismatch silently disables RAG.
- **LLM citation IDs are allow-list validated server-side** — the server generates `S1`..`Sn` IDs for each search result and only accepts those back from the LLM. Any fabricated IDs are dropped silently. This is a security/accuracy control, not a convenience.
- **`JsonTicketRepository` uses an in-memory dict as primary store** — there is no database; all filtering/sorting happens in Python on the full in-memory set. This does not scale beyond ~10k tickets.
- **Ticket writes are serialized by a `threading.RLock`** — the app is single-process (uvicorn `--reload`); multi-process deployment would require a real database.
- **Settings singleton is module-level** in `main.py** (`settings = get_settings()`) — CORS middleware is configured once at module load, not per-request.
- **`_ServiceUnavailable` is a private exception** in `api/rag.py`, not in `domain/errors.py` — its handler is registered in `main.py` after a late import (intentional `# noqa: E402`). Don't move it without updating the handler registration order.
- **Chroma vs Numpy vector stores are functionally equivalent** — Numpy is in-memory/file-based (simple, no daemon), Chroma is persistent (required for large indexes). Both implement `VectorStorePort` via Protocol.
- **Privacy boundary is enforced only by convention** — `build_ticket_query()` manually strips sensitive fields before RAG/LLM. There is no framework-level enforcement; reviewers must check this in code review.
