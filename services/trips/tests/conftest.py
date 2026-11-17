import pytest

import config
import db
import migrate


@pytest.fixture(scope="session")
def migrated_db():
    if not config.DATABASE_URL:
        pytest.fail("DATABASE_URL is not set: these tests need a running SQL Server (see README)")
    migrate.run()


@pytest.fixture
def temp_db(migrated_db):
    # Empties the tables before each test (children first). Point DATABASE_URL at a throwaway database.
    with db.transaction() as cursor:
        cursor.execute("DELETE FROM tasks")
        cursor.execute("DELETE FROM members")
        cursor.execute("DELETE FROM trips")
    yield
