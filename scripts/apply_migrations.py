#!/usr/bin/env python
"""Applies any supabase/migrations/*.sql file not yet recorded in
schema_migrations. Run after pulling changes that add a new migration —
Supabase CLI isn't in use here, so nothing applies these automatically.

Usage (from repo root):
    python scripts/apply_migrations.py
Reads DATABASE_URL from apps/api/.env (same asyncpg-style connection string
the backend uses) or the environment.
"""

import asyncio
import os
import pathlib
import re

import asyncpg

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"


def _load_database_url() -> str:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    env_file = REPO_ROOT / "apps" / "api" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()

    raise SystemExit("DATABASE_URL not found in environment or apps/api/.env")


def _to_asyncpg_dsn(sqlalchemy_url: str) -> dict:
    # postgresql+asyncpg://user:pass@host:port/db -> asyncpg.connect(**kwargs)
    match = re.match(
        r"postgresql\+asyncpg://([^:]+):(.+)@([^:/]+):(\d+)/(.+)", sqlalchemy_url
    )
    if not match:
        raise SystemExit(f"Couldn't parse DATABASE_URL: {sqlalchemy_url!r}")
    user, password, host, port, database = match.groups()
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": int(port),
        "database": database,
        "statement_cache_size": 0,
    }


async def main() -> None:
    conn = await asyncpg.connect(**_to_asyncpg_dsn(_load_database_url()))
    try:
        await conn.execute(
            """
            create table if not exists public.schema_migrations (
                filename text primary key,
                applied_at timestamptz not null default now()
            )
            """
        )
        applied = {row["filename"] for row in await conn.fetch("select filename from public.schema_migrations")}

        pending = sorted(
            f for f in MIGRATIONS_DIR.glob("*.sql") if f.name not in applied
        )
        if not pending:
            print("Nothing to apply — schema is up to date.")
            return

        for path in pending:
            print(f"Applying {path.name} ...")
            await conn.execute(path.read_text(encoding="utf-8"))
            await conn.execute(
                "insert into public.schema_migrations (filename) values ($1)", path.name
            )
            print("  OK")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
