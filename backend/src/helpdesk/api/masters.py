import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from helpdesk.config import Settings, get_settings
from helpdesk.domain.errors import NotFoundError
from helpdesk.domain.models import MasterResponse

router = APIRouter(prefix="/masters", tags=["masters"])


class MasterName(StrEnum):
    categories = "categories"
    priorities = "priorities"
    support_teams = "support-teams"
    statuses = "statuses"
    handling_types = "handling-types"
    inquiry_types = "inquiry-types"


def read_master(settings: Settings, key: str) -> list[dict[str, Any]]:
    masters_path = Path(settings.SEED_DATA_DIR) / "masters.json"
    if not masters_path.exists():
        raise NotFoundError(f"Master file not found at {masters_path}")

    try:
        data = json.loads(masters_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise NotFoundError(f"Failed to read master data: {e}") from e

    if key not in data:
        raise NotFoundError(f"Master category '{key}' not found in master data")
    items: list[dict[str, Any]] = data[key]
    return items


@router.get("/{master_name}", response_model=MasterResponse)
def get_master(
    master_name: MasterName,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    key = master_name.value
    return {"name": key, "items": read_master(settings, key)}
