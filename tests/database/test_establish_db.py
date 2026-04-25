import sqlite3
import sys
from contextlib import closing
from importlib import reload
from pkgutil import iter_modules
from pathlib import Path

import pytest

import database
import database.establish_db as establish_db


@pytest.fixture
def isolated_db_schema(tmp_path, monkeypatch):
    original_schema = list(establish_db.EXPECTED_SCHEMA)
    establish_db.EXPECTED_SCHEMA.clear()

    db_path = tmp_path / "test_app.db"
    monkeypatch.setattr(establish_db, "DATABASE", str(db_path))

    yield db_path

    establish_db.EXPECTED_SCHEMA.clear()
    establish_db.EXPECTED_SCHEMA.extend(original_schema)


def _get_column_names(db_path, table_name):
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _get_table_sql(db_path, table_name):
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
    return "" if row is None or row[0] is None else row[0]


def test_get_connection_closes_after_context_exit(isolated_db_schema):
    with establish_db.get_connection() as conn:
        conn.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_get_connection_raw_returns_usable_connection(isolated_db_schema):
    conn = establish_db.get_connection_raw()
    try:
        row = conn.execute("SELECT 1").fetchone()
        assert row is not None
        assert row[0] == 1
    finally:
        conn.close()

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_ensure_schema_creates_database_and_table(isolated_db_schema):
    establish_db.register_table(
        establish_db.Table(
            name="example_table",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
                establish_db.SQLColumn("name", "TEXT NOT NULL"),
            ),
            primary_key=("id",),
        )
    )

    establish_db.ensure_schema()

    assert isolated_db_schema.exists()
    assert _get_column_names(isolated_db_schema, "example_table") == {"id", "name"}


def test_ensure_schema_adds_new_column_to_existing_table(isolated_db_schema):
    initial_schema = establish_db.Table(
        name="example_table",
        columns=(
            establish_db.SQLColumn("id", "INTEGER"),
            establish_db.SQLColumn("name", "TEXT NOT NULL"),
        ),
        primary_key=("id",),
    )
    establish_db.register_table(initial_schema)
    establish_db.ensure_schema()

    establish_db.EXPECTED_SCHEMA.clear()
    expanded_schema = establish_db.Table(
        name="example_table",
        columns=(
            establish_db.SQLColumn("id", "INTEGER"),
            establish_db.SQLColumn("name", "TEXT NOT NULL"),
            establish_db.SQLColumn("status", "TEXT DEFAULT 'ACTIVE'"),
        ),
        primary_key=("id",),
    )
    establish_db.register_table(expanded_schema)

    establish_db.ensure_schema()

    assert _get_column_names(isolated_db_schema, "example_table") == {
        "id",
        "name",
        "status",
    }


def test_database_package_import_registers_tables_module_schemas():
    module_file = establish_db.__file__
    assert module_file is not None
    tables_path = Path(module_file).with_name("tables")
    discovered_modules = [
        module_info.name
        for module_info in iter_modules([str(tables_path)])
        if not module_info.ispkg
    ]

    for module_name in discovered_modules:
        sys.modules.pop(f"database.tables.{module_name}", None)

    original_schema = list(establish_db.EXPECTED_SCHEMA)
    establish_db.EXPECTED_SCHEMA.clear()
    try:
        reload(database)
        for module_name in discovered_modules:
            assert f"database.tables.{module_name}" in sys.modules

        # Each schema module should register at least one table.
        assert len(establish_db.EXPECTED_SCHEMA) >= len(discovered_modules)
    finally:
        establish_db.EXPECTED_SCHEMA.clear()
        establish_db.EXPECTED_SCHEMA.extend(original_schema)


def test_table_create_sql_optionally_includes_named_extra_constraints():
    table = establish_db.Table(
        name="child",
        columns=(
            establish_db.SQLColumn("id", "INTEGER NOT NULL"),
            establish_db.SQLColumn("parent_id", "INTEGER NOT NULL"),
        ),
        primary_key=("id",),
        extra_constraints=(
            establish_db.SQLColumn(
                "fk_child_parent",
                "FOREIGN KEY (parent_id) REFERENCES parent(id)",
            ),
        ),
    )

    base_sql = table.create_sql()
    with_constraints_sql = table.create_sql(include_extra_constraints=True)

    assert "PRIMARY KEY (id)" in base_sql
    assert "CONSTRAINT fk_child_parent" not in base_sql
    assert "CONSTRAINT fk_child_parent FOREIGN KEY (parent_id) REFERENCES parent(id)" in with_constraints_sql


def test_ensure_schema_rebuilds_table_to_add_named_constraints_and_preserves_rows(isolated_db_schema):
    establish_db.register_table(
        establish_db.Table(
            name="parent",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
                establish_db.SQLColumn("name", "TEXT NOT NULL"),
            ),
            primary_key=("id",),
        )
    )
    establish_db.register_table(
        establish_db.Table(
            name="child",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
                establish_db.SQLColumn("parent_id", "INTEGER NOT NULL"),
            ),
            primary_key=("id",),
        )
    )
    establish_db.ensure_schema()

    with establish_db.get_connection() as conn:
        conn.execute("INSERT INTO parent (id, name) VALUES (1, 'p1')")
        conn.execute("INSERT INTO child (id, parent_id) VALUES (1, 1)")
        conn.commit()

    establish_db.EXPECTED_SCHEMA.clear()
    establish_db.register_table(
        establish_db.Table(
            name="parent",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
                establish_db.SQLColumn("name", "TEXT NOT NULL"),
            ),
            primary_key=("id",),
        )
    )
    establish_db.register_table(
        establish_db.Table(
            name="child",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
                establish_db.SQLColumn("parent_id", "INTEGER NOT NULL"),
            ),
            primary_key=("id",),
            extra_constraints=(
                establish_db.SQLColumn(
                    "fk_child_parent",
                    "FOREIGN KEY (parent_id) REFERENCES parent(id)",
                ),
            ),
        )
    )
    establish_db.ensure_schema()

    with establish_db.get_connection() as conn:
        assert establish_db.constraint_exists(conn, "child", "fk_child_parent")
        row_count = conn.execute("SELECT COUNT(*) AS count FROM child").fetchone()["count"]
        assert row_count == 1

    establish_db.ensure_schema()
    table_sql = _get_table_sql(isolated_db_schema, "child")
    assert table_sql.count("CONSTRAINT fk_child_parent") == 1


def test_ensure_schema_rejects_invalid_constraint_names(isolated_db_schema):
    establish_db.register_table(
        establish_db.Table(
            name="example",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
            ),
            primary_key=("id",),
            extra_constraints=(
                establish_db.SQLColumn("bad-name", "CHECK (id > 0)"),
            ),
        )
    )

    with pytest.raises(ValueError, match="Invalid constraint name"):
        establish_db.ensure_schema()


def test_ensure_schema_rejects_invalid_table_names(isolated_db_schema):
    establish_db.register_table(
        establish_db.Table(
            name="bad-table",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
            ),
            primary_key=("id",),
        )
    )

    with pytest.raises(ValueError, match="Invalid table name"):
        establish_db.ensure_schema()


def test_ensure_schema_rejects_invalid_primary_key_column_names(isolated_db_schema):
    establish_db.register_table(
        establish_db.Table(
            name="example",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
            ),
            primary_key=("id-column",),
        )
    )

    with pytest.raises(ValueError, match="Invalid primary key column name"):
        establish_db.ensure_schema()


def test_add_extra_constraints_logs_operational_error(isolated_db_schema, capsys):
    establish_db.register_table(
        establish_db.Table(
            name="example",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
            ),
            primary_key=("id",),
        )
    )
    establish_db.ensure_schema()

    establish_db.EXPECTED_SCHEMA.clear()
    establish_db.register_table(
        establish_db.Table(
            name="example",
            columns=(
                establish_db.SQLColumn("id", "INTEGER"),
            ),
            primary_key=("id",),
            extra_constraints=(
                establish_db.SQLColumn("fk_broken", "FOREIGN KEY ("),
            ),
        )
    )

    establish_db.ensure_schema()

    output = capsys.readouterr().out
    assert "Failed to add constraints on 'example': fk_broken" in output
    assert "Foreign key references missing column" in output
