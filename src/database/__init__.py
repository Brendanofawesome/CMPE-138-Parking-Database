from .establish_db import (
    DATABASE,
    EXPECTED_SCHEMA,
    SQLColumn,
    Table,
    ensure_schema,
    register_table,
    _import_table_modules,
)


_import_table_modules(__name__)
