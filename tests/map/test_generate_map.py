from pathlib import Path
import sqlite3
from typing import Iterator

from PIL import Image, ImageChops
import pytest

from app.map.generate_map import (
    generate_map,
    get_lot_data,
    get_lot_data_info,
    lot_data_info,
    put_default_lots,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_DATA_DIR = REPO_ROOT / "src" / "app" / "map" / "map_data"
EXPECTED_FINAL_MAP = MAP_DATA_DIR / "final_map.png"
GENERATED_FINAL_MAP = MAP_DATA_DIR / "final_map_test.png"


def _assert_png_matches_expected(actual_path: Path, expected_path: Path) -> None:
    assert actual_path.exists(), f"Generated image is missing: {actual_path}"
    assert expected_path.exists(), f"Expected baseline image is missing: {expected_path}"

    with Image.open(actual_path) as actual, Image.open(expected_path) as expected:
        assert actual.size == expected.size, (
            f"Image sizes differ for {actual_path.name}: "
            f"generated={actual.size}, expected={expected.size}"
        )

        actual_rgba = actual.convert("RGBA")
        expected_rgba = expected.convert("RGBA")
        diff = ImageChops.difference(actual_rgba, expected_rgba)
        assert diff.getbbox() is None, f"Pixel output differs for {actual_path.name}"


@pytest.fixture
def db_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        """
        CREATE TABLE location (
            location_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_name TEXT NOT NULL,
            manager INTEGER,
            manager_contact TEXT,
            cost_cents INTEGER NOT NULL,
            x_coordinate INTEGER NOT NULL,
            y_coordinate INTEGER NOT NULL,
            data_name TEXT NOT NULL UNIQUE
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE parking_spot (
            location_id INTEGER NOT NULL,
            spot_id TEXT NOT NULL,
            active BOOLEAN NOT NULL,
            location_description TEXT,
            type TEXT NOT NULL,
            box_x_min INTEGER NOT NULL,
            box_x_max INTEGER NOT NULL,
            box_y_min INTEGER NOT NULL,
            box_y_max INTEGER NOT NULL,
            PRIMARY KEY (location_id, spot_id)
        )
        """
    )

    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def clean_generated_final_map() -> None:
    if GENERATED_FINAL_MAP.exists():
        GENERATED_FINAL_MAP.unlink()


def test_put_default_lots_then_get_lot_data_info_returns_expected_entries(db_conn: sqlite3.Connection) -> None:
    put_default_lots(db_conn)

    lots = get_lot_data_info(db_conn)

    assert len(lots) == 3
    assert {lot.data_name for lot in lots} == {"lot1", "lot2", "lot3"}


def test_get_lot_data_rejects_path_traversal_data_name() -> None:
    with pytest.raises(ValueError, match="Invalid data name"):
        get_lot_data(MAP_DATA_DIR, lot_data_info(1, 0, 0, "../outside"))


def test_generate_map_rejects_path_traversal_base_map_name(db_conn: sqlite3.Connection) -> None:
    put_default_lots(db_conn)

    with pytest.raises(ValueError, match="Invalid base map name"):
        generate_map(db_conn, MAP_DATA_DIR, "..\\outside", "final_map_test")


def test_generate_map_matches_expected_final_map_baseline(db_conn: sqlite3.Connection) -> None:
    put_default_lots(db_conn)

    generate_map(db_conn, MAP_DATA_DIR, "map_base", "final_map_test")

    _assert_png_matches_expected(GENERATED_FINAL_MAP, EXPECTED_FINAL_MAP)

    spot_count = db_conn.execute("SELECT COUNT(*) FROM parking_spot").fetchone()[0]
    assert spot_count > 0
