"""Repository paths resolved from this file, never from the process CWD."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "db" / "novel_anima.db"
DATA_DIR = ROOT / "data"
SOURCES_DIR = DATA_DIR / "sources"
PLANS_DIR = DATA_DIR / "plans"
REVIEWS_DIR = DATA_DIR / "reviews"
CHARACTERS_DIR = DATA_DIR / "characters"
WARDROBE_DIR = DATA_DIR / "wardrobe"
PROMPTS_DIR = ROOT / "prompts"
CONFIG_DIR = ROOT / "config"
SOURCES_CONFIG = CONFIG_DIR / "catalog" / "sources.json"
SCHEMA_PATH = ROOT / "sql" / "schema_v1.sql"
MIGRATIONS_DIR = ROOT / "sql" / "migrations"
