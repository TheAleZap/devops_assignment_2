import os

import migrate


def test_pending_returns_unapplied_sql_files_in_name_order():
    files = ["002_add_column.sql", "001_init.sql", "README.md", "003_backfill.sql"]
    assert migrate.pending(files, {"001_init.sql"}) == ["002_add_column.sql", "003_backfill.sql"]


def test_pending_is_empty_when_everything_is_applied():
    assert migrate.pending(["001_init.sql"], {"001_init.sql"}) == []


def test_split_batches_splits_on_go_lines_and_drops_empty_batches():
    sql = "CREATE TABLE a (id INT);\nGO\n\ngo\nALTER TABLE a ADD b INT;\n"
    assert migrate.split_batches(sql) == ["CREATE TABLE a (id INT);\n", "\nALTER TABLE a ADD b INT;\n"]


def test_split_batches_keeps_a_file_without_go_as_one_batch():
    assert migrate.split_batches("CREATE TABLE a (id INT);") == ["CREATE TABLE a (id INT);"]


def test_migrations_folder_starts_with_001_init():
    assert sorted(os.listdir(migrate.MIGRATIONS_DIR))[0] == "001_init.sql"
