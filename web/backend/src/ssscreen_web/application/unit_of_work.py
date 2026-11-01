from __future__ import annotations

from sqlalchemy.orm import Session


class UnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> UnitOfWork:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
