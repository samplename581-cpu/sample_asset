# AGENTS.md — Ask Mode (Documentation / Q&A)

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Documentation Context

- **`frontend/`** is NOT a Node.js app — it's plain HTML/JS/CSS with no package.json or build step, served as static files directly by FastAPI's `StaticFiles` mount at `/`.
- **RAG is optional at runtime** — if `make index` has never been run, the app starts normally but `/api/v1/rag/*` endpoints return 503. This is by design.
- **"seed data" vs "runtime data"**: `data/seed/` is read-only source data checked into git; `data/runtime/` is a gitignored mutable copy created at first startup. Modifying seed files does not affect a running instance until the runtime file is deleted.
- **`data/index/`** holds the numpy vector index (`chunks.json`, `vectors.npy`, `manifest.json`) built by `make index`; Chroma stores its index under `chroma-data/` (also gitignored).
- **Provider selection is purely via env vars** — there is no runtime API to switch providers; the selection is locked at startup via `get_settings()` lru_cache.
- **`DraftAnswerResponse.needs_human_confirmation` is always `True`** — the field exists for the response schema but is never set to `False` anywhere in the codebase; the LLM output is always a draft.
- **`requester_department` on `Ticket` is deprecated** — the field exists only for backward compatibility with old JSON files; new tickets do not populate it.
