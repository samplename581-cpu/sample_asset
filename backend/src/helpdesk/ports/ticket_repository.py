from typing import Protocol

from helpdesk.domain.models import Ticket, TicketCreate, TicketPage, TicketUpdate


class TicketRepository(Protocol):
    def list_tickets(
        self,
        status: str | None = None,
        category: str | None = None,
        assigned_team: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> TicketPage: ...

    def get_ticket(self, ticket_id: str) -> Ticket: ...
    def create_ticket(self, data: TicketCreate) -> Ticket: ...
    def update_ticket(self, ticket_id: str, data: TicketUpdate) -> Ticket: ...
