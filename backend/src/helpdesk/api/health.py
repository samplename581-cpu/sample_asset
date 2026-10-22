import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from helpdesk.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger("helpdesk.api.health")


class LiveResponse(BaseModel):
    status: str = "ok"


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/live", response_model=LiveResponse)
def get_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=ReadinessResponse)
def get_ready(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    checks: dict[str, str] = {}

    seed_dir = Path(settings.SEED_DATA_DIR)
    runtime_dir = Path(settings.RUNTIME_DATA_DIR)
    index_dir = Path(settings.INDEX_DIR)

    checks["seed_dir"] = "ok" if seed_dir.exists() else "missing"
    checks["runtime_dir"] = "ok" if runtime_dir.exists() else "missing"
    checks["seed_tickets"] = "ok" if (seed_dir / settings.TICKET_SEED_FILE).exists() else "missing"

    if settings.VECTOR_STORE_PROVIDER in ("chroma", "milvus"):
        # DB-backed stores: rag_service が起動時に接続・検証済みであることを確認する
        checks["rag_service"] = (
            "ok" if getattr(request.app.state, "rag_service", None) is not None else "unavailable"
        )
    else:
        # NumPy: local index manifest の存在と dimension の整合を確認する
        checks["index_dir"] = "ok" if index_dir.exists() else "missing"
        checks["index"] = _check_numpy_index(index_dir, settings.EMBEDDING_DIMENSION)

    is_ready = all(v == "ok" for v in checks.values())

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": checks}

    return {"status": "ready", "checks": checks}


def _check_numpy_index(index_dir: Path, expected_dimension: int) -> str:
    """NumPy index manifest を検証して check 値を返す。

    ファイルが存在しない場合は "missing"、
    dimension が不一致の場合は "dimension_mismatch"、
    正常の場合は "ok" を返す。
    JSON デコードエラー・型エラーは "invalid_manifest" として返す。
    """
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        return "missing"

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read index manifest: %s", exc)
        return "invalid_manifest"

    manifest_dim = manifest.get("dimension")
    if not isinstance(manifest_dim, int):
        logger.warning("Index manifest has non-integer dimension: %r", manifest_dim)
        return "invalid_manifest"

    if manifest_dim != expected_dimension:
        return "dimension_mismatch"

    return "ok"
