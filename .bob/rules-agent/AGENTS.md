# AGENTS.md — Agent Mode (Coding)

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Coding Rules

- **Never instantiate adapters directly in services or API layers** — always use `app.state.*` (wired in `main.py` lifespan) or the factory functions `create_llm()` / `_create_embedding()`.
- **Adding a new adapter**: implement the `Protocol` in `ports/` structurally, then add a new `case` in `factory.py` (LLM) or `_create_embedding()` in `main.py` (Embedding). No base class to inherit.
- **Domain errors map to HTTP status codes** via registered exception handlers in `main.py`; raise the correct subclass: `NotFoundError`→404, `ConflictError`→409, `ValidationError`→422, `ProviderError`→503.
- **`TicketUpdate` uses `exclude_unset=True`** when calling `model_dump()` — only pass fields that were actually set, not all fields with `None`.
- **`JsonTicketRepository` is in-memory + file** — in-memory dict is the source of truth at runtime; `_save_atomic()` persists via `os.replace()`. Never write to `data/runtime/tickets.json` directly in code.
- **`get_settings()` is cached** — if you change env vars in a test, call `get_settings.cache_clear()` explicitly (or rely on the `reset_settings_cache` autouse fixture).
- **`from __future__ import annotations`** must be the first import in every new module — it's enforced by ruff UP but also needed for `Protocol` forward refs under Python 3.14.
- **Pydantic models with `extra="forbid"`**: `TicketCreate`, `TicketUpdate`, `DraftAnswerRequest` — do not add fields without updating the model.
- **`uv run` prefix required** for all Python tool invocations (pytest, ruff, mypy) — do not use bare `python`/`pytest`.
