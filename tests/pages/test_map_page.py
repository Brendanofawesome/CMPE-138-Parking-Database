"""Tests for the map home page and related routes."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing

import pytest

from app.auth import create_user
from app.flask import create_app
from database import establish_db


@pytest.fixture()
def map_app(tmp_path, monkeypatch):
    db_path = tmp_path / "map.db"
    monkeypatch.setattr(establish_db, "DATABASE", str(db_path))
    establish_db.ensure_schema()

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            INSERT INTO location (lot_name, manager, manager_contact, hourly_cost_cents, x_coordinate, y_coordinate, data_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("Lot 1", None, None, 500, 100, 200, "lot1"),
        )
        conn.execute(
            """
            INSERT INTO location (lot_name, manager, manager_contact, hourly_cost_cents, x_coordinate, y_coordinate, data_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("Lot 2", None, None, 700, 300, 400, "lot2"),
        )
        conn.execute(
            """
            INSERT INTO parking_spot (location_id, spot_id, active, location_description, type, box_x_min, box_x_max, box_y_min, box_y_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "A1", 1, "", "EV", 10, 30, 10, 40),
        )
        conn.execute(
            """
            INSERT INTO parking_spot (location_id, spot_id, active, location_description, type, box_x_min, box_x_max, box_y_min, box_y_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "A2", 1, "", "Regular", 40, 60, 10, 40),
        )
        conn.execute(
            """
            INSERT INTO parking_spot (location_id, spot_id, active, location_description, type, box_x_min, box_x_max, box_y_min, box_y_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "A3", 1, "", "Handicap", 70, 90, 10, 40),
        )
        conn.execute(
            """
            INSERT INTO parking_spot (location_id, spot_id, active, location_description, type, box_x_min, box_x_max, box_y_min, box_y_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (2, "A1", 1, "", "EV", 110, 130, 10, 40),
        )
        conn.commit()

    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    app = create_app(get_connection)
    app.config["WTF_CSRF_ENABLED"] = False
    return app, db_path


def test_map_shows_login_links_when_logged_out(map_app):
    app, _db_path = map_app

    with app.test_client() as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert b"Login" in response.data
    assert b"Create Account" in response.data


def _extract_spot_data(html: bytes) -> list[dict[str, object]]:
    match = re.search(rb"const spotData = (\[.*?\]);", html, flags=re.DOTALL)
    assert match is not None
    return json.loads(match.group(1).decode("utf-8"))


def test_map_shows_username_and_spot_metadata_when_logged_in(map_app):
    app, db_path = map_app

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        session_cookie = create_user(conn, "map_user", b"password123", "555-0199")
        current_user_id = conn.execute(
            "SELECT user_id FROM user WHERE username = ?",
            ("map_user",),
        ).fetchone()["user_id"]
        conn.execute(
            """
            INSERT INTO user (username, password_hash, hash_algorithm, salt, phone_number)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("other_user", b"hash", "argon2id", b"salt", "555-0101"),
        )
        other_user_id = conn.execute(
            "SELECT user_id FROM user WHERE username = ?",
            ("other_user",),
        ).fetchone()["user_id"]

        conn.execute(
            """
            INSERT INTO parking_session (user_id, location_id, spot_id, status, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (int(current_user_id), 1, "A1", "ON_HOLD", "2026-04-26T08:00:00+00:00", None),
        )
        conn.execute(
            """
            INSERT INTO parking_session (user_id, location_id, spot_id, status, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (int(other_user_id), 1, "A2", "ON_HOLD", "2026-04-26T08:30:00+00:00", None),
        )
        conn.commit()

    assert session_cookie is not None

    with app.test_client() as client:
        client.set_cookie("session_id", session_cookie)
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert b"Signed in as map_user" in response.data
    assert b"Logout" in response.data
    assert b"Payments" in response.data
    assert b"Parking Sessions" in response.data
    assert b'"spot_id": "A1"' in response.data
    assert b'"location_id": 1' in response.data
    assert b'"location_name": "Lot 1"' in response.data
    assert b'"is_booked": true' in response.data
    assert b'"is_booked": false' in response.data
    assert b'"is_booked_by_current_user": true' in response.data
    assert b'"is_booked_by_current_user": false' in response.data
    assert b"your-booking" in response.data


def test_map_booking_state_does_not_leak_across_lots_for_same_spot_id(map_app):
    app, db_path = map_app

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        session_cookie = create_user(conn, "lot_user", b"password123", "555-0198")
        user_row = conn.execute(
            "SELECT user_id FROM user WHERE username = ?",
            ("lot_user",),
        ).fetchone()
        assert user_row is not None

        conn.execute(
            """
            INSERT INTO parking_session (user_id, location_id, spot_id, status, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (int(user_row["user_id"]), 1, "A1", "ON_HOLD", "2026-04-26T07:00:00+00:00", None),
        )
        conn.commit()

    assert session_cookie is not None

    with app.test_client() as client:
        client.set_cookie("session_id", session_cookie)
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    spots = _extract_spot_data(response.data)
    a1_rows = [spot for spot in spots if spot["spot_id"] == "A1"]
    assert len(a1_rows) == 2

    spot_by_location = {
        int(spot["location_id"]): spot
        for spot in a1_rows
    }
    assert bool(spot_by_location[1]["is_booked"]) is True
    assert bool(spot_by_location[1]["is_booked_by_current_user"]) is True
    assert bool(spot_by_location[2]["is_booked"]) is False
    assert bool(spot_by_location[2]["is_booked_by_current_user"]) is False


def test_parking_sessions_page_shows_only_active_rows(map_app):
    app, db_path = map_app

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        session_cookie = create_user(conn, "sessions_user", b"password123", "555-0210")
        user_row = conn.execute(
            "SELECT user_id FROM user WHERE username = ?",
            ("sessions_user",),
        ).fetchone()
        assert user_row is not None
        user_id = int(user_row["user_id"])

        conn.execute( #active session
            """
            INSERT INTO parking_session (user_id, location_id, spot_id, status, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, 1, "A1", "IN_SESSION", "534253452", None),
        )
        conn.execute( #inactive session
            """
            INSERT INTO parking_session (user_id, location_id, spot_id, status, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, 1, "A2", "COMPLETED", "12341234", "12"),
        )
        conn.commit()

    assert session_cookie is not None

    with app.test_client() as client:
        client.set_cookie("session_id", session_cookie)
        response = client.get("/parking-sessions", follow_redirects=False)

    assert response.status_code == 200
    assert b"Active Sessions" in response.data
    assert b"Spot A1" in response.data
    assert b"Spot A2" not in response.data


def test_final_map_image_route_serves_png(map_app):
    app, _db_path = map_app

    with app.test_client() as client:
        response = client.get("/map/final-map", follow_redirects=False)

    assert response.status_code == 200
    assert response.mimetype == "image/png"
