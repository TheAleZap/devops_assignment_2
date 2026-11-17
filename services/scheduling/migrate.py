import logging
import os
import re

import db

log = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

CREATE_MIGRATIONS_TABLE = """
IF OBJECT_ID('schema_migrations', 'U') IS NULL
CREATE TABLE schema_migrations (
    version NVARCHAR(255) NOT NULL PRIMARY KEY,
    applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
)
"""


def pending(files, applied):
    return [name for name in sorted(files) if name.endswith(".sql") and name not in applied]


def split_batches(sql):
    batches = re.split(r"^\s*GO\s*$", sql, flags=re.MULTILINE | re.IGNORECASE)
    return [batch for batch in batches if batch.strip()]


def run():
    with db.transaction() as cursor:
        cursor.execute(CREATE_MIGRATIONS_TABLE)
    with db.transaction() as cursor:
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row["version"] for row in cursor.fetchall()}

    todo = pending(os.listdir(MIGRATIONS_DIR), applied)
    if not todo:
        log.info("Migrations: database up to date (%d applied)", len(applied))
        return

    for name in todo:
        with open(os.path.join(MIGRATIONS_DIR, name), encoding="utf-8") as file:
            sql = file.read()
        with db.transaction() as cursor:
            for batch in split_batches(sql):
                cursor.execute(batch)
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (name,))
        log.info("Migrations: applied %s", name)
