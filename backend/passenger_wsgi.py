"""File di avvio per cPanel "Setup Python App" (Passenger). Vedi docs/07-deploy-netsons.md."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.migrate import migrate_on_startup

migrate_on_startup()

from app.main import create_app  # noqa: E402
from app.wsgi import build_wsgi_app  # noqa: E402

application = build_wsgi_app(create_app())
