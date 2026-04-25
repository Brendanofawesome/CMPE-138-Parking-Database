import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from importlib import import_module
from pkgutil import iter_modules

DATABASE = str(Path(__file__).resolve().parents[2] / "app.db")

############################
# MODULAR SCHEMA REFERENCE #
############################

SCHEMA_ALLOWED_CHARACTERS: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_"

#defines an SQL Column to be registered
@dataclass(frozen=True, slots=True)
class SQLColumn:
    name: str
    attribute_list: str

#defines the datatype for a SQL table to be registered
@dataclass(frozen=True, slots=True)
class Table:
    name: str
    columns: tuple[SQLColumn, ...] = ()
    primary_key: tuple[str, ...] | None = None
    extra_constraints: tuple[SQLColumn, ...] = ()

    def create_sql(self, include_extra_constraints: bool = False, table_name: str | None = None) -> str:
        create_table_name = table_name if table_name is not None else self.name
        parts = [
            f"{column.name} {column.attribute_list}"
            for column in self.columns
        ]

        if self.primary_key:
            parts.append(f"PRIMARY KEY ({', '.join(self.primary_key)})")

        if include_extra_constraints:
            parts.extend(
                f"CONSTRAINT {constraint.name} {constraint.attribute_list}"
                for constraint in self.extra_constraints
            )

        return f"CREATE TABLE IF NOT EXISTS {create_table_name} ({', '.join(parts)})"

    def column_definitions(self) -> tuple[SQLColumn, ...]:
        return self.columns

    def constraint_definitions(self) -> tuple[SQLColumn, ...]:
        return self.extra_constraints

EXPECTED_SCHEMA: list[Table] = [] #stores schema (append using register_table())

# register a table to the schema reference
def register_table(table: Table) -> None:
    EXPECTED_SCHEMA.append(table)


############################
# Database Usage Functions #
############################

#get a connection handle to the database
@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

#must be manually closed
def get_connection_raw() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    return conn

###########################
# Database Initialization #
###########################

def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_schema
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def get_existing_columns(conn: sqlite3.Connection, table_name: str) -> dict[str, dict[str, int | str | None]]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {
        row["name"]: {
            "type": row["type"],
            "notnull": row["notnull"],
            "default": row["dflt_value"],
            "pk": row["pk"],
        }
        for row in rows
    }


def ensure_table(conn: sqlite3.Connection, table: Table) -> None:
    table_name = table.name
    if not all(char in SCHEMA_ALLOWED_CHARACTERS for char in table_name):
        raise ValueError(f"Invalid table name: {table_name!r}")

    if table.primary_key is not None:
        for primary_key_column in table.primary_key:
            if not all(char in SCHEMA_ALLOWED_CHARACTERS for char in primary_key_column):
                raise ValueError(f"Invalid primary key column name: {primary_key_column!r}")
    
    if not table_exists(conn, table_name):
        print(f"Creating table: {table_name}")
        conn.execute(table.create_sql())
        return

    existing_columns = get_existing_columns(conn, table_name)

    for column in table.column_definitions():
        if not all(char in SCHEMA_ALLOWED_CHARACTERS for char in column.name):
            raise ValueError(f"Invalid column name: {column.name!r}")
        
        if column.name not in existing_columns:
            print(f"    Adding missing column '{column.name}' to '{table_name}'")
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column.attribute_list}"
            )


def get_table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        """
        SELECT sql
        FROM sqlite_schema
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row["sql"] if row is not None and row["sql"] is not None else ""


def constraint_exists(conn: sqlite3.Connection, table_name: str, constraint_name: str) -> bool:
    table_sql = get_table_sql(conn, table_name)
    return f"CONSTRAINT {constraint_name}" in table_sql


def _rebuild_table_with_constraints(conn: sqlite3.Connection, table: Table) -> None:
    temp_table_name = f"__tmp_{table.name}"
    column_names = [column.name for column in table.column_definitions()]
    column_list = ", ".join(column_names)

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute(f"DROP TABLE IF EXISTS {temp_table_name}")
        conn.execute(table.create_sql(include_extra_constraints=True, table_name=temp_table_name))
        conn.execute(
            f"INSERT INTO {temp_table_name} ({column_list}) SELECT {column_list} FROM {table.name}"
        )
        conn.execute(f"DROP TABLE {table.name}")
        conn.execute(f"ALTER TABLE {temp_table_name} RENAME TO {table.name}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def add_extra_constraints(conn: sqlite3.Connection, table: Table) -> None:
    if not table.extra_constraints:
        return

    missing_constraint_names: list[str] = []
    for constraint in table.constraint_definitions():
        if not all(char in SCHEMA_ALLOWED_CHARACTERS for char in constraint.name):
            raise ValueError(f"Invalid constraint name: {constraint.name!r}")

        if not constraint_exists(conn, table.name, constraint.name):
            missing_constraint_names.append(constraint.name)

    if not missing_constraint_names:
        return

    try:
        _rebuild_table_with_constraints(conn, table)
    except sqlite3.OperationalError as error:
        print(f"Failed to add constraints on '{table.name}': {', '.join(missing_constraint_names)}")
        print("Foreign key references missing column")
        print(f"SQLite error: {error}")


def ensure_schema() -> None:
    db_file_created = Path(DATABASE).exists()

    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 1000")

        for table in EXPECTED_SCHEMA:
            ensure_table(conn, table)

        for table in EXPECTED_SCHEMA:
            add_extra_constraints(conn, table)

        conn.commit()

    if db_file_created:
        print("Schema check complete.")
    else:
        print("Database created and schema initialized.")


#helper to grab the schema defined in ./tables/
def _import_table_modules(package_name: str = "database") -> None:
    
    tables_path = Path(__file__).with_name("tables")
    package_prefix = f"{package_name}.tables"

    for module_info in iter_modules([str(tables_path)]):
        if not module_info.ispkg:
            import_module(f"{package_prefix}.{module_info.name}")


if __name__ == "__main__":
    import sys # pylint: disable=import-outside-toplevel
    SRC_PATH = str(Path(__file__).resolve().parents[1])
    if SRC_PATH not in sys.path:
        sys.path.insert(0, SRC_PATH)

    _import_table_modules()
    ensure_schema()
