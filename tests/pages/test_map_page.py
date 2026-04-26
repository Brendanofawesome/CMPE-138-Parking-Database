"""Tests for the map home page and related routes."""

from __future__ import annotations

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
            INSERT INTO parking_spot (location_id, spot_id, active, location_description, type, box_x_min, box_x_max, box_y_min, box_y_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "A1", 1, "", "EV", 10, 30, 10, 40),
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


def test_map_shows_username_and_spot_metadata_when_logged_in(map_app):
    app, db_path = map_app

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        session_cookie = create_user(conn, "map_user", b"password123", "555-0199")

    assert session_cookie is not None

    with app.test_client() as client:
        client.set_cookie("session_id", session_cookie)
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert b"Signed in as map_user" in response.data
    assert b"Logout" in response.data
    assert b'"spot_id": "A1"' in response.data
    assert b'"location_id": 1' in response.data
    assert b'"location_name": "Lot 1"' in response.data


def test_final_map_image_route_serves_png(map_app):
    app, _db_path = map_app

    with app.test_client() as client:
        response = client.get("/map/final-map", follow_redirects=False)

    assert response.status_code == 200
    assert response.mimetype == "image/png"
