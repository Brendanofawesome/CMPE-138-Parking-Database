"""Integration tests for account creation, login, and session cookies."""

import sqlite3
from contextlib import closing

import pytest

from app.auth import create_user
from app.flask import create_app
from database import establish_db


@pytest.fixture()
def auth_app(tmp_path, monkeypatch):
    db_path = tmp_path / "auth_flow.db"
    monkeypatch.setattr(establish_db, "DATABASE", str(db_path))
    establish_db.ensure_schema()

    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    app = create_app(get_connection)
    app.config["WTF_CSRF_ENABLED"] = False

    return app, db_path


def _cookie_value_from_response(response) -> str:
    set_cookie_header = response.headers.get("Set-Cookie")
    assert set_cookie_header is not None
    return set_cookie_header.split(";", 1)[0].split("=", 1)[1]


def test_create_account_creates_user_and_issues_session_cookie(auth_app):
    app, db_path = auth_app

    with app.test_client() as client:
        response = client.post(
            "/create-account",
            data={
                "username": "new_user",
                "phone_number": "555-0100",
                "password": "password123",
                "confirm_password": "password123",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    session_cookie = _cookie_value_from_response(response)
    assert session_cookie

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        user_row = conn.execute(
            "SELECT username, phone_number FROM user WHERE username = ?",
            ("new_user",),
        ).fetchone()

    assert user_row is not None
    assert user_row["username"] == "new_user"
    assert user_row["phone_number"] == "555-0100"


def test_login_issues_session_cookie_for_existing_user(auth_app):
    app, db_path = auth_app

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        seeded_cookie = create_user(conn, "login_user", b"password123", "555-0111")

    assert seeded_cookie is not None

    with app.test_client() as client:
        response = client.post(
            "/login",
            data={
                "username": "login_user",
                "password": "password123",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    session_cookie = _cookie_value_from_response(response)
    assert session_cookie


def test_session_cookie_is_verified_on_followup_request(auth_app):
    app, db_path = auth_app

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        session_cookie = create_user(conn, "cookie_user", b"password123", "555-0122")

    assert session_cookie is not None

    with app.test_client() as client:
        client.set_cookie("session_id", session_cookie)
        response = client.get(
            "/login",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"