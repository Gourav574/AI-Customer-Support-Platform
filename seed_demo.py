"""Populate development-only demo accounts, teams, tickets and KB entries."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.database import engine
from backend.app import models  # noqa: F401
from backend.app.main import seed_demo
from alembic.config import Config
from alembic import command

command.upgrade(Config(str(ROOT/"alembic.ini")),"head")
seed_demo()
print("Development sample data is ready. Credentials are documented in README.md.")
