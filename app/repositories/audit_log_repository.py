from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        self.session.flush()
        return log

    def list_by_task_id(self, task_id: str, limit: int = 50) -> list[AuditLog]:
        return list(
            self.session.query(AuditLog)
            .filter(AuditLog.task_id == task_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
