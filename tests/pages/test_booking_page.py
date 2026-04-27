"""Tests for booking endpoint hour validation and fee calculation."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from app.auth import create_user
from app.flask import create_app
from database import establish_db


@pytest.fixture()
def booking_app(tmp_path, monkeypatch):
    db_path = tmp_path / "booking.db"
    monkeypatch.setattr(establish_db, "DATABASE", str(db_path))
    establish_db.ensure_schema()

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            INSERT INTO location (lot_name, manager, manager_contact, hourly_cost_cents, x_coordinate, y_coordinate, data_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("Lot 1", None, None, 500, 10, 20, "lot1"),
        )
        conn.execute(
            """
            INSERT INTO parking_spot (location_id, spot_id, active, location_description, type, box_x_min, box_x_max, box_y_min, box_y_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "A1", 1, "", "Regular", 1, 2, 3, 4),
        )
        conn.commit()

    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    app = create_app(get_connection)
    app.config["WTF_CSRF_ENABLED"] = False
    return app, db_path


def _login_cookie(db_path) -> str:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cookie = create_user(conn, "book_user", b"password123", "555-1000")
    assert cookie is not None
    return cookie


@pytest.mark.parametrize(
    "hours,error_text",
    [
        (None, b"Missing hours."),
        ("abc", b"Invalid hours."),
        (0.5, b"Hours must be at least 1.0."),
        (1.2, b"Hours must be in 0.5-hour increments."),
    ],
)
def test_book_spot_rejects_invalid_hours(booking_app, hours, error_text):
    app, db_path = booking_app
    session_cookie = _login_cookie(db_path)

    payload = {
        "spot_id": "A1",
        "location_id": 1,
        "licence_value": "BOOK123",
        "licence_state": "CA",
    }
    if hours is not None:
        payload["hours"] = hours

    with app.test_client() as client:
        client.set_cookie("session_id", session_cookie)
        response = client.post("/book-spot", json=payload)

    assert response.status_code == 400
    assert error_text in response.data


@pytest.mark.parametrize("hours,expected_cost", [(1.0, 5.0), (1.5, 7.5), (2.0, 10.0)])
def test_book_spot_accepts_half_hour_increments_and_computes_fee(booking_app, hours, expected_cost):
    app, db_path = booking_app
    session_cookie = _login_cookie(db_path)

    with app.test_client() as client:
        client.set_cookie("session_id", session_cookie)
        response = client.post(
            "/book-spot",
            json={
                "spot_id": "A1",
                "location_id": 1,
                "hours": hours,
                "licence_value": "BOOK123",
                "licence_state": "CA",
            },
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert data["hours"] == hours
    assert data["cost"] == expected_cost

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        fee_row = conn.execute(
            "SELECT amount FROM fee WHERE fee_id = ?",
            (data["fee_id"],),
        ).fetchone()
        vehicle_row = conn.execute(
            "SELECT user_id FROM vehicle WHERE Licence_Value = ? AND Licence_State = ?",
            ("BOOK123", "CA"),
        ).fetchone()
        session_row = conn.execute(
            "SELECT Licence_Value, Licence_State FROM parking_session WHERE session_id = ?",
            (data["session_id"],),
        ).fetchone()

    assert fee_row is not None
    assert float(fee_row["amount"]) == expected_cost
    assert vehicle_row is not None
    assert session_row is not None
    assert str(session_row["Licence_Value"]) == "BOOK123"
    assert str(session_row["Licence_State"]) == "CA"
