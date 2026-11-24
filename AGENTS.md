# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Stack

- **Python 3.14 strictly** (`requires-python = ">=3.14,<3.15"`) — no other Python version works
- **Package manager**: `uv` only (not pip/poetry). Install: `uv sync --extra dev`
- **Backend**: FastAPI + Pydantic v2 + pydantic-settings; app entrypoint is `helpdesk.main:app` in `backend/src/`
- **Frontend**: Plain HTML/JS/CSS in `frontend/` — no build step, served as static files by FastAPI

## Commands

```bash
make setup          # cp .env.example .env + uv sync --extra dev
make dev            # uvicorn on 127.0.0.1:8000 with --reload
make test           # uv run pytest backend/tests -v
make lint           # ruff check --fix
make typecheck      # mypy backend/src --ignore-missing-imports
make seed           # export seed data from business tools Excel
make index          # build vector index (required before RAG works)
```

**Single test**: `uv run pytest backend/tests/unit/test_rag_service.py -v`  
**Single test function**: `uv run pytest backend/tests/unit/test_rag_service.py::test_name -v`

## Architecture

Ports-and-adapters (Hexagonal) layout:

```
domain/models.py + errors.py   ← pure domain, no I/O
ports/                          ← Protocol interfaces (LLMPort, EmbeddingPort, VectorStorePort, TicketRepository)
adapters/                       ← implementations: mock | watsonx | local/openai_compatible | chroma | numpy
services/                       ← RagService, TicketService (use ports, not adapters directly)
api/                            ← FastAPI routers; access adapters only via app.state
```

Adapters are wired at startup in `main.py` lifespan; services receive them via `app.state.*`.

## Critical Patterns

- **Ports are `Protocol`**, not ABC. New adapters must implement all methods structurally (duck typing).
- **`get_settings()` is `@lru_cache`** — tests MUST call `get_settings.cache_clear()` before and after (the `reset_settings_cache` autouse fixture in `conftest.py` does this automatically).
- **Ticket updates require `version`** (optimistic locking). `TicketUpdate.version` must match current `Ticket.version` or raises `ConflictError` (409).
- **Privacy**: `customer_name`, `customer_email`, `order_number`, `notes` must NOT be passed to embedding, vector store, LLM prompt, or logs. Only `inquiry_type`, `product_name`, `description` go into `build_ticket_query()`.
- **`needs_human_confirmation` is always `True`** — never override this in `DraftAnswerResponse`.
- **LLM citation IDs are allow-list validated** — LLM-returned `citation_ids` outside the server's `citation_map` are silently dropped (design section 11.3).
- **`CORS_ORIGINS=*` is blocked** when `APP_ENV` is not `development` or `test`.
- **`TICKET_SEED_FILE`** must be a bare filename (no path separators); a `model_validator` enforces this.
- **RAG index dimension must match `EMBEDDING_DIMENSION`** in `.env`; mismatch silently disables RAG (logs error, returns `None`).

## Code Style

- `ruff` enforces E, F, I (isort), UP (pyupgrade), B (bugbear), S (bandit), N (pep8-naming); line length 100
- `mypy --strict` required; all public functions need type annotations
- `from __future__ import annotations` at top of every source file
- Domain errors: raise `helpdesk.domain.errors.*` (not built-in exceptions) so FastAPI exception handlers return RFC 9457 `application/problem+json`
- All JSON writes use `ensure_ascii=False, indent=2`; file writes use atomic `os.replace(tmp, target)` pattern

## Testing

- `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio`
- Tests live in `backend/tests/`; `conftest.py` sets `EMBEDDING_PROVIDER=mock`, `LLM_PROVIDER=mock`, `VECTOR_STORE_PROVIDER=numpy` via `os.environ` **before any helpdesk imports**
- Use `tmp_seed_dir`, `tmp_runtime_dir`, `tmp_index_dir` fixtures (from `conftest.py`) — never read/write `data/` in tests
- Integration tests in `backend/tests/integration/` require real provider credentials; skip in CI without them

## Provider Selection (`.env`)

| Setting | Options |
|---|---|
| `LLM_PROVIDER` | `mock` (default) · `watsonx` · `openai_compatible` · `local` |
| `EMBEDDING_PROVIDER` | `mock` · `watsonx` · `local` |
| `VECTOR_STORE_PROVIDER` | `chroma` (default) · `numpy` |

watsonx requires `WATSONX_URL`, `WATSONX_PROJECT_ID`, `WATSONX_API_KEY`, `WATSONX_MODEL_ID` — validated at startup.
