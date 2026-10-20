import base64
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from helpdesk.domain.errors import ConflictError, NotFoundError
from helpdesk.domain.models import Ticket, TicketCreate, TicketPage, TicketUpdate


class JsonTicketRepository:
    """JSON-based repository implementing TicketRepository port with in-memory caching and atomic file writes."""

    def __init__(
        self, seed_data_dir: str = "./data/seed", runtime_data_dir: str = "./data/runtime"
    ) -> None:
        self.seed_file = Path(seed_data_dir) / "tickets.json"
        self.runtime_dir = Path(runtime_data_dir)
        self.runtime_file = self.runtime_dir / "tickets.json"
        self._tickets: dict[str, Ticket] = {}
        self._init_storage()

    def _init_storage(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if not self.runtime_file.exists():
            if self.seed_file.exists():
                shutil.copyfile(self.seed_file, self.runtime_file)
            else:
                self.runtime_file.write_text("[]", encoding="utf-8")
        self._load()

    def _load(self) -> None:
        if not self.runtime_file.exists():
            self._tickets = {}
            return
        content = self.runtime_file.read_text(encoding="utf-8")
        if not content.strip():
            self._tickets = {}
            return
        raw_items = json.loads(content)
        self._tickets = {item["ticket_id"]: Ticket.model_validate(item) for item in raw_items}

    def _save_atomic(self) -> None:
        items = [ticket.model_dump(mode="json") for ticket in self._tickets.values()]
        payload = json.dumps(items, ensure_ascii=False, indent=2)

        # Write to temporary file in the same directory, then atomic rename
        with tempfile.NamedTemporaryFile(
            "w", dir=self.runtime_dir, delete=False, encoding="utf-8"
        ) as tf:
            tf.write(payload)
            temp_name = tf.name

        os.replace(temp_name, self.runtime_file)

    @staticmethod
    def _encode_cursor(index: int) -> str:
        return base64.urlsafe_b64encode(str(index).encode("utf-8")).decode("utf-8")

    @staticmethod
    def _decode_cursor(cursor: str) -> int:
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
            return int(decoded)
        except Exception:
            return 0

    def list_tickets(
        self,
        status: str | None = None,
        category: str | None = None,
        assigned_team: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> TicketPage:
        # Filter
        filtered = [
            t
            for t in self._tickets.values()
            if (status is None or t.status == status)
            and (category is None or t.category == category)
            and (assigned_team is None or t.assigned_team == assigned_team)
        ]

        # Sort: created_at desc, ticket_id asc
        sorted_tickets = sorted(
            filtered,
            key=lambda t: (-t.created_at.timestamp(), t.ticket_id),
        )

        offset = 0
        if cursor:
            offset = self._decode_cursor(cursor)

        page_items = sorted_tickets[offset : offset + limit]
        next_offset = offset + limit
        next_cursor = (
            self._encode_cursor(next_offset) if next_offset < len(sorted_tickets) else None
        )

        return TicketPage(items=page_items, next_cursor=next_cursor)

    def get_ticket(self, ticket_id: str) -> Ticket:
        if ticket_id not in self._tickets:
            raise NotFoundError(f"Ticket with ID '{ticket_id}' not found")
        return self._tickets[ticket_id]

    def _generate_next_ticket_id(self) -> str:
        max_num = 0
        for tid in self._tickets.keys():
            if tid.startswith("TKT-"):
                num_part = tid[4:]
                if num_part.isdigit():
                    max_num = max(max_num, int(num_part))
        return f"TKT-{max_num + 1:08d}"

    def create_ticket(self, data: TicketCreate) -> Ticket:
        ticket_id = self._generate_next_ticket_id()
        now = datetime.now(UTC)
        ticket = Ticket(
            ticket_id=ticket_id,
            title=data.title,
            description=data.description,
            created_at=now,
            requester_department=data.requester_department,
            category=None,
            priority=None,
            status="新規",
            assigned_team=None,
            resolution=None,
            version=1,
        )
        self._tickets[ticket_id] = ticket
        self._save_atomic()
        return ticket

    def update_ticket(self, ticket_id: str, data: TicketUpdate) -> Ticket:
        current = self.get_ticket(ticket_id)
        if current.version != data.version:
            raise ConflictError(
                f"Version conflict on ticket '{ticket_id}': expected {data.version}, but current version is {current.version}"
            )

        update_dict = data.model_dump(exclude_unset=True)
        # version in update_dict is the input version, which will be incremented
        update_dict.pop("version", None)

        current_data = current.model_dump()
        current_data.update(update_dict)
        current_data["version"] = current.version + 1

        updated = Ticket.model_validate(current_data)
        self._tickets[ticket_id] = updated
        self._save_atomic()
        return updated
