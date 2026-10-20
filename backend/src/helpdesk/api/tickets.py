from fastapi import APIRouter, Header, Path, Query, Request, Response, status

from helpdesk.domain.models import Ticket, TicketCreate, TicketPage, TicketUpdate
from helpdesk.services.ticket_service import TicketService

_TICKET_ID_PATH = Path(
    ...,
    pattern=r"^[A-Z0-9][A-Z0-9_-]{2,39}$",
    description="Ticket ID (e.g. DEV-001, TKT-00000001)",
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_service(request: Request) -> TicketService:
    repo = request.app.state.ticket_repository
    return TicketService(repo)


@router.get("", response_model=TicketPage)
def list_tickets(
    request: Request,
    status: str | None = Query(None, max_length=40),
    category: str | None = Query(None, max_length=40),
    assigned_team: str | None = Query(None, max_length=80),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=500),
) -> TicketPage:
    service = get_ticket_service(request)
    return service.list_tickets(
        status=status,
        category=category,
        assigned_team=assigned_team,
        limit=limit,
        cursor=cursor,
    )


@router.post("", response_model=Ticket, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: TicketCreate,
    request: Request,
    response: Response,
) -> Ticket:
    service = get_ticket_service(request)
    ticket = service.create_ticket(data)
    response.headers["Location"] = f"{request.url.path}/{ticket.ticket_id}"
    return ticket


@router.get("/{ticket_id}", response_model=Ticket)
def get_ticket(
    request: Request,
    ticket_id: str = _TICKET_ID_PATH,
) -> Ticket:
    service = get_ticket_service(request)
    return service.get_ticket(ticket_id)


@router.patch("/{ticket_id}", response_model=Ticket)
def update_ticket(
    data: TicketUpdate,
    request: Request,
    ticket_id: str = _TICKET_ID_PATH,
    content_type: str | None = Header(None),
) -> Ticket:
    # Accept application/merge-patch+json or application/json
    service = get_ticket_service(request)
    return service.update_ticket(ticket_id, data)
