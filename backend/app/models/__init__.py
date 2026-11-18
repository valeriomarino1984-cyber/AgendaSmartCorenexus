"""Modelli ORM. Ogni nuovo modulo con modelli va importato qui, così Alembic li vede."""

from app.models.accounts import (  # noqa: F401
    AuditLog,
    AuthSession,
    BusinessType,
    Membership,
    RateLimitEvent,
    Tenant,
    TenantSettings,
    User,
    UserToken,
)
from app.models.agenda import (  # noqa: F401
    Appointment,
    AppointmentEvent,
    Availability,
    AvailabilityException,
)
from app.models.catalog import (  # noqa: F401
    Client,
    ClientConsentEvent,
    Location,
    Professional,
    Service,
    ServiceProfessional,
)
