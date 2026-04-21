import sys
from pathlib import Path
from pkgutil import iter_modules

import database.establish_db as establish_db
import pytest


@pytest.fixture
def isolated_db_schema(tmp_path, monkeypatch):
    original_schema = list(establish_db.EXPECTED_SCHEMA)
    establish_db.EXPECTED_SCHEMA.clear()

    tables_path = Path(establish_db.__file__).with_name("tables")
    for module_info in iter_modules([str(tables_path)]):
        if not module_info.ispkg:
            sys.modules.pop(f"database.tables.{module_info.name}", None)

    db_path = tmp_path / "test_app.db"
    monkeypatch.setattr(establish_db, "DATABASE", str(db_path))

    yield db_path

    establish_db.EXPECTED_SCHEMA.clear()
    establish_db.EXPECTED_SCHEMA.extend(original_schema)
