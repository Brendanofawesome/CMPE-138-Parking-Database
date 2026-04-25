"""Tests for the admin plate-check page."""

from __future__ import annotations

import sqlite3

import pytest

from app.flask import create_app
from database import establish_db


@pytest.fixture()
def admin_app(tmp_path, monkeypatch):
    db_path = tmp_path / "admin.db"
    monkeypatch.setattr(establish_db, "DATABASE", str(db_path))
    establish_db.ensure_schema()

    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    app = create_app(get_connection)
    app.config["WTF_CSRF_ENABLED"] = False
    return app


def test_admin_plate_check_page_renders_form(admin_app):
    with admin_app.test_client() as client:
        response = client.get("/admin/plate-check", follow_redirects=False)

    assert response.status_code == 200
    assert b"Plate Checking & Ticketing" in response.data
    assert b"Enter License Plate" in response.data
    assert b"Check Plate" in response.data


def test_admin_plate_check_page_reports_missing_plate(admin_app):
    with admin_app.test_client() as client:
        response = client.post(
            "/admin/plate-check",
            data={"plate": "NOPE123", "action": "check"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert b"No session found for this plate." in response.data


def test_admin_plate_check_page_shows_session_details(admin_app):
    with admin_app.test_client() as client:
        response = client.post(
            "/admin/plate-check",
            data={"plate": "XYZ789", "action": "check"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert b"Found session for XYZ789" in response.data
    assert b"Session Details" in response.data
    assert b"Plate: XYZ789" in response.data
    assert b"Spot: B2" in response.data
    assert b"Status: expired" in response.data


def test_admin_plate_check_page_issues_ticket_for_expired_session(admin_app):
    with admin_app.test_client() as client:
        response = client.post(
            "/admin/plate-check",
            data={"plate": "XYZ789", "action": "issue_ticket"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert b"Ticket issued!" in response.data
    assert b"Ticket Issued" in response.data
    assert b"Plate: XYZ789" in response.data
    assert b"Amount: $50.0" in response.data


def test_admin_plate_check_page_rejects_issue_ticket_for_active_session(admin_app):
    with admin_app.test_client() as client:
        response = client.post(
            "/admin/plate-check",
            data={"plate": "ABC123", "action": "issue_ticket"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert b"Session is not expired." in response.data
