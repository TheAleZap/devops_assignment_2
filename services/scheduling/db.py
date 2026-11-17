import logging
import time
from contextlib import contextmanager
from urllib.parse import unquote, urlsplit

import pymssql

import config

log = logging.getLogger(__name__)


def connection_settings(url):
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    parts = urlsplit(url)
    return {
        "server": parts.hostname,
        "port": str(parts.port or 1433),
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": parts.path.lstrip("/"),
    }


def get_connection(retries=None):
    attempts = config.DB_CONNECT_RETRIES if retries is None else retries
    settings = connection_settings(config.DATABASE_URL)
    delay = 1
    for attempt in range(1, attempts + 1):
        try:
            return pymssql.connect(**settings, login_timeout=10, timeout=30)
        except (pymssql.OperationalError, pymssql.InterfaceError) as error:
            if attempt == attempts:
                raise
            log.warning(
                "Database not reachable (attempt %d/%d), retrying in %ds: %s",
                attempt, attempts, delay, error,
            )
            time.sleep(delay)
            delay = min(delay * 2, 10)


@contextmanager
def transaction(retries=None):
    conn = get_connection(retries)
    try:
        cursor = conn.cursor(as_dict=True)
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check():
    conn = get_connection(retries=1)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_migrations")
        cursor.fetchone()
        cursor.execute("INSERT INTO schema_migrations (version) VALUES ('__health_probe__')")
        conn.rollback()
    finally:
        conn.close()
