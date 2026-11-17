from __future__ import annotations

import sentry_sdk

from app.core.config import Settings


def init_sentry(settings: Settings) -> None:
    if settings.sentry_dsn is None:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.environment,
        send_default_pii=False,  # nessun dato personale (IP, header, body) inviato a Sentry
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
