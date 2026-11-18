"""Registro attività (audit_logs): chi ha fatto cosa, quando, da quale IP."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.accounts import AuditLog


def audit(
    session: Session,
    action: str,
    *,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    resource: str | None = None,
    resource_id: str | uuid.UUID | None = None,
    details: dict[str, object] | None = None,
    ip: str | None = None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id is not None else None,
            details=details,
            ip=ip,
        )
    )
