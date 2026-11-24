import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from helpdesk.adapters.embedding_mock import MockEmbeddingAdapter
from helpdesk.adapters.factory import create_llm
from helpdesk.adapters.sheet_excel import ExcelSheetExporter
from helpdesk.adapters.ticket_json import JsonTicketRepository
from helpdesk.adapters.vector_numpy import NumpyVectorStore
from helpdesk.api.health import router as health_router
from helpdesk.api.masters import router as masters_router
from helpdesk.api.rag import router as rag_router
from helpdesk.api.tickets import router as tickets_router
from helpdesk.config import get_settings
from helpdesk.domain.errors import (
    ConflictError,
    HelpdeskError,
    NotFoundError,
    ProviderError,
    ValidationError,
)
from helpdesk.ports.embeddings import EmbeddingPort
from helpdesk.ports.vector_store import ChunkRecord
from helpdesk.services.rag_service import RagService

logger = logging.getLogger("helpdesk")


def _create_embedding(settings: Any) -> EmbeddingPort:
    """Factory: create EmbeddingPort from settings. Raises ConfigurationError on unknown provider."""
    from helpdesk.domain.errors import ConfigurationError as HelpdeskConfigError

    provider = settings.EMBEDDING_PROVIDER
    if provider == "local":
        from helpdesk.adapters.embedding_local import LocalEmbeddingAdapter

        return LocalEmbeddingAdapter(settings.EMBEDDING_MODEL_ID)
    elif provider == "watsonx":
        from helpdesk.adapters.embedding_watsonx import WatsonxEmbeddingAdapter

        return WatsonxEmbeddingAdapter.from_settings(settings)
    elif provider == "mock":
        return MockEmbeddingAdapter()
    else:
        raise HelpdeskConfigError(
            f"Unsupported EMBEDDING_PROVIDER: '{provider}'. Use 'mock', 'local', or 'watsonx'."
        )


def _load_rag_service(settings: Any) -> RagService | None:
    """Load index from disk and build RagService. Returns None if index is missing.

    Validates manifest against settings before loading to prevent silent mismatches.
    """
    from pathlib import Path

    import numpy as np

    embedding = _create_embedding(settings)

    if settings.VECTOR_STORE_PROVIDER == "chroma":
        try:
            from helpdesk.adapters.vector_chroma import ChromaVectorStore

            chroma_store = ChromaVectorStore.from_settings(settings)
            logger.info(
                "RAG service connected to local Chroma: collection=%s rows=%d",
                settings.CHROMA_COLLECTION,
                chroma_store.count(),
            )
            return RagService(embedding=embedding, store=chroma_store)
        except Exception as exc:
            logger.error(
                "Failed to open local Chroma: error_type=%s",
                exc.__class__.__name__,
            )
            return None

    if settings.VECTOR_STORE_PROVIDER != "numpy":
        logger.error("Unsupported VECTOR_STORE_PROVIDER: %s", settings.VECTOR_STORE_PROVIDER)
        return None

    index_dir = Path(settings.INDEX_DIR)
    manifest_path = index_dir / "manifest.json"
    chunks_path = index_dir / "chunks.json"
    vectors_path = index_dir / "vectors.npy"

    if not (manifest_path.exists() and chunks_path.exists() and vectors_path.exists()):
        logger.warning("RAG index not found in %s – run 'make index' first", index_dir)
        return None

    try:
        # --- Manifest validation ---
        manifest: dict[str, object] = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_dim = int(str(manifest.get("dimension", 0)))
        manifest_provider = str(manifest.get("embedding_provider", ""))
        manifest_model = str(manifest.get("embedding_model", ""))

        if manifest_dim != settings.EMBEDDING_DIMENSION:
            logger.error(
                "Index dimension mismatch: manifest=%d, EMBEDDING_DIMENSION=%d. "
                "Run 'make index' to rebuild.",
                manifest_dim,
                settings.EMBEDDING_DIMENSION,
            )
            return None

        # Warn if provider/model has changed (soft check – doesn't block loading)
        if manifest_provider != settings.EMBEDDING_PROVIDER:
            logger.warning(
                "Index was built with provider=%s but EMBEDDING_PROVIDER=%s. "
                "Consider rebuilding the index.",
                manifest_provider,
                settings.EMBEDDING_PROVIDER,
            )

        # --- Load chunks and vectors ---
        chunks_raw: list[dict[str, object]] = json.loads(chunks_path.read_text(encoding="utf-8"))
        chunks = [
            ChunkRecord(
                chunk_id=str(c["chunk_id"]),
                document_id=str(c["document_id"]),
                text=str(c["text"]),
                title=str(c["title"]),
                source=str(c["source"]),
                document_type=str(c["document_type"]),
                category=str(c["category"]) if c.get("category") is not None else None,
                position=int(str(c["position"])),
                faq_id=str(c["faq_id"]) if c.get("faq_id") is not None else None,
                completion_policy=(
                    str(c["completion_policy"]) if c.get("completion_policy") is not None else None
                ),
            )
            for c in chunks_raw
        ]
        vectors: np.ndarray = np.load(str(vectors_path))

        # Validate vector shape consistency
        if vectors.shape[0] != len(chunks):
            logger.error(
                "Index corrupted: vectors.shape[0]=%d != chunk_count=%d. Rebuild index.",
                vectors.shape[0],
                len(chunks),
            )
            return None
        if vectors.shape[1] != manifest_dim:
            logger.error(
                "Index corrupted: vectors.shape[1]=%d != manifest dimension=%d. Rebuild index.",
                vectors.shape[1],
                manifest_dim,
            )
            return None

        numpy_store = NumpyVectorStore(chunks=chunks, vectors=vectors)
        logger.info(
            "RAG index loaded: chunks=%d dim=%d provider=%s model=%s",
            numpy_store.count(),
            manifest_dim,
            manifest_provider,
            manifest_model,
        )
        return RagService(embedding=embedding, store=numpy_store)
    except Exception as exc:
        logger.error("Failed to load RAG index: %s", exc)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.ticket_repository = JsonTicketRepository(
        seed_data_dir=settings.SEED_DATA_DIR,
        runtime_data_dir=settings.RUNTIME_DATA_DIR,
        seed_file_name=settings.TICKET_SEED_FILE,
    )
    sheet_exporter = ExcelSheetExporter(
        template_path=settings.SHEET_TEMPLATE_PATH,
        output_path=settings.SHEET_OUTPUT_PATH,
    )
    # 起動時に見出し行を検査する（問題があれば警告を出すが起動は止めない）
    try:
        import openpyxl as _openpyxl

        _wb = _openpyxl.load_workbook(settings.SHEET_TEMPLATE_PATH)
        _header_row, _col_map = sheet_exporter._detect_header(_wb.worksheets[0])
        if _header_row is None:
            logger.warning(
                "sheet_exporter: テンプレートに見出し行が見つかりません。"
                "template_path=%s",
                settings.SHEET_TEMPLATE_PATH,
            )
        else:
            required = {"受付番号", "受付日時", "お客様名", "問い合わせ内容（要約）", "ステータス"}
            missing = required - set(_col_map.keys())
            if missing:
                logger.warning(
                    "sheet_exporter: テンプレートに必須見出しがありません: %s。"
                    "template_path=%s",
                    missing,
                    settings.SHEET_TEMPLATE_PATH,
                )
    except Exception as _exc:
        logger.warning(
            "sheet_exporter: テンプレート検査でエラーが発生しました (%s)。"
            "template_path=%s",
            type(_exc).__name__,
            settings.SHEET_TEMPLATE_PATH,
        )
    app.state.sheet_exporter = sheet_exporter
    app.state.rag_service = _load_rag_service(settings)
    app.state.llm = create_llm(settings)
    yield
    # Shutdown: close resources
    rag_service = getattr(app.state, "rag_service", None)
    if rag_service is not None:
        rag_service.close()
    llm = getattr(app.state, "llm", None)
    close = getattr(llm, "close", None)
    if callable(close):
        await close()


app = FastAPI(
    title="Helpdesk RAG Starter API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

settings = get_settings()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID and Structured Logging Middleware
@app.middleware("http")
async def logging_and_request_id_middleware(request: Request, call_next: Any) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.perf_counter()

    try:
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        log_data = {
            "request_id": request_id,
            "event": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "outcome": "success" if response.status_code < 400 else "error",
        }
        logger.info(json.dumps(log_data, ensure_ascii=False))
        return response
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        log_data = {
            "request_id": request_id,
            "event": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
            "duration_ms": duration_ms,
            "outcome": "exception",
            "error_type": exc.__class__.__name__,
        }
        logger.error(json.dumps(log_data, ensure_ascii=False))
        raise


def get_current_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


# RFC 9457 Problem Details Exception Handlers
@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    request_id = get_current_request_id(request)
    problem = {
        "type": "https://helpdesk.example.com/problems/not-found",
        "title": "Not Found",
        "status": status.HTTP_404_NOT_FOUND,
        "detail": exc.detail,
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=problem,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    request_id = get_current_request_id(request)
    problem = {
        "type": "https://helpdesk.example.com/problems/conflict",
        "title": "Conflict",
        "status": status.HTTP_409_CONFLICT,
        "detail": exc.detail,
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=problem,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(ValidationError)
async def custom_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    request_id = get_current_request_id(request)
    problem = {
        "type": "https://helpdesk.example.com/problems/validation-error",
        "title": "Validation Error",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": exc.detail,
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def fastapi_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = get_current_request_id(request)
    problem = {
        "type": "https://helpdesk.example.com/problems/validation-error",
        "title": "Validation Error",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": str(exc),
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    request_id = get_current_request_id(request)
    problem = {
        "type": "https://helpdesk.example.com/problems/service-unavailable",
        "title": "Service Unavailable",
        "status": status.HTTP_503_SERVICE_UNAVAILABLE,
        "detail": exc.detail,
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=problem,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(HelpdeskError)
async def generic_helpdesk_error_handler(request: Request, exc: HelpdeskError) -> JSONResponse:
    request_id = get_current_request_id(request)
    problem = {
        "type": "https://helpdesk.example.com/problems/unprocessable-entity",
        "title": "Unprocessable Entity",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": exc.detail,
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )


# Register Routers
app.include_router(health_router, prefix=settings.API_PREFIX)
app.include_router(tickets_router, prefix=settings.API_PREFIX)
app.include_router(masters_router, prefix=settings.API_PREFIX)
app.include_router(rag_router, prefix=settings.API_PREFIX)

# Serve frontend static files if the directory exists (ビルド不要の最小 UI)
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")


# 503 handler for missing RAG index (_ServiceUnavailable from api/rag.py)
from helpdesk.api.rag import _ServiceUnavailable  # noqa: E402


@app.exception_handler(_ServiceUnavailable)
async def rag_unavailable_handler(request: Request, exc: _ServiceUnavailable) -> JSONResponse:
    request_id = get_current_request_id(request)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "type": "https://helpdesk.example.com/problems/service-unavailable",
            "title": "Service Unavailable",
            "status": status.HTTP_503_SERVICE_UNAVAILABLE,
            "detail": "RAG index is not loaded. Run build_index.py first.",
            "request_id": request_id,
        },
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )
