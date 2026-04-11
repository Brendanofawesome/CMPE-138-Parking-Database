import sqlite3
import sys
from contextlib import contextmanager
from typing import Iterator
from dataclasses import dataclass
from pathlib import Path #to check if the database exists

DATABASE = "app.db"

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
    extra_constraints: tuple[str, ...] = ()

    def create_sql(self) -> str:
        parts = [
            f"{column.name} {column.attribute_list}"
            for column in self.columns
        ]
        parts.extend(self.extra_constraints)
        return f"CREATE TABLE IF NOT EXISTS {self.name} ({', '.join(parts)})"

    def column_definitions(self) -> tuple[SQLColumn, ...]:
        return self.columns

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
    if(not all(char in SCHEMA_ALLOWED_CHARACTERS for char in table_name)):
        raise ValueError(f"Invalid table name: {table_name!r}")
    
    if not table_exists(conn, table_name):
        print(f"Creating table: {table_name}")
        conn.execute(table.create_sql())
        return

    existing_columns = get_existing_columns(conn, table_name)

    for column in table.column_definitions():
        if(not all(char in SCHEMA_ALLOWED_CHARACTERS for char in column.name)):
            raise ValueError(f"Invalid column name: {column.name!r}")
        
        if column.name not in existing_columns:
            print(f"    Adding missing column '{column.name}' to '{table_name}'")
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column.attribute_list}"
            )


def ensure_schema() -> None:
    db_file_created = Path(DATABASE).exists()

    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")

        for table in EXPECTED_SCHEMA:
            ensure_table(conn, table)

        conn.commit()

    if db_file_created:
        print("Schema check complete.")
    else:
        print("Database created and schema initialized.")


#helper to grab the schema defined in ./tables/
def _import_table_modules(package_name: str = "database") -> None:
    from importlib import import_module
    from pkgutil import iter_modules
    
    tables_path = Path(__file__).with_name("tables")
    package_prefix = f"{package_name}.tables"

    for module_info in iter_modules([str(tables_path)]):
        if not module_info.ispkg:
            import_module(f"{package_prefix}.{module_info.name}")


if __name__ == "__main__":
    src_path = str(Path(__file__).resolve().parents[1])
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from database import establish_db as database_module

    _import_table_modules()
    database_module.ensure_schema()