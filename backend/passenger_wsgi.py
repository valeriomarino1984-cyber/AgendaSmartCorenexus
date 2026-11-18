"""File di avvio per cPanel "Setup Python App" (Passenger). Vedi docs/07-deploy-netsons.md."""

import os
import sys

# Passenger raccoglie solo stderr (in stderr.log) e può chiudere stdout: ogni stampa su stdout
# farebbe fallire l'avvio con BrokenPipeError, quindi la si devia su stderr.
sys.stdout = sys.stderr
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.logging import configure_logging  # noqa: E402
from app.core.migrate import migrate_on_startup  # noqa: E402

configure_logging(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    json_logs=os.environ.get("LOG_JSON", "true").lower() == "true",
)
migrate_on_startup()

from app.main import create_app  # noqa: E402
from app.wsgi import build_wsgi_app  # noqa: E402

application = build_wsgi_app(create_app())
