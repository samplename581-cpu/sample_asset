from helpdesk.domain.models import Ticket, TicketCreate, TicketPage, TicketUpdate
from helpdesk.ports.ticket_repository import TicketRepository


class TicketService:
    def __init__(self, repository: TicketRepository) -> None:
        self.repository = repository

    def list_tickets(
        self,
        status: str | None = None,
        category: str | None = None,
        assigned_team: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> TicketPage:
        return self.repository.list_tickets(
            status=status,
            category=category,
            assigned_team=assigned_team,
            limit=limit,
            cursor=cursor,
        )

    def get_ticket(self, ticket_id: str) -> Ticket:
        return self.repository.get_ticket(ticket_id)

    def create_ticket(self, data: TicketCreate) -> Ticket:
        return self.repository.create_ticket(data)

    def update_ticket(self, ticket_id: str, data: TicketUpdate) -> Ticket:
        return self.repository.update_ticket(ticket_id, data)
