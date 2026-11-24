from typing import Protocol

from helpdesk.domain.models import Ticket


class SheetExporter(Protocol):
    """Port: Excelシートへのチケット書き出しを抽象化する。"""

    def append_ticket(self, ticket: Ticket) -> None:
        """チケット1件を出力ファイルの最初の空き行に追記する。
        同じ ticket_id がすでに存在する場合はスキップ（冪等）。
        """
        ...

    def rebuild(self, tickets: list[Ticket]) -> None:
        """テンプレートから出力ファイルを作り直し、全チケットを古い順に書き込む。"""
        ...
