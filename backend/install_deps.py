"""Installa le dipendenze nel virtualenv dell'app.

Si esegue da cPanel → Setup Python App → Execute python script. Alternativa a "Run Pip Install",
che su alcuni server non installa nulla. Al termine verifica che i moduli si importino.
"""

import os
import subprocess
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
print("Python in uso:", sys.executable, sys.version.split()[0])
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"],
    capture_output=True,
    text=True,
    check=False,
)
print(result.stdout[-3000:])
print(result.stderr[-3000:])
for module in [
    "fastapi",
    "sqlalchemy",
    "pymysql",
    "alembic",
    "structlog",
    "a2wsgi",
    "pydantic_settings",
]:
    try:
        __import__(module)
        print("OK   ", module)
    except Exception as exc:
        print("MANCA", module, "->", exc)
