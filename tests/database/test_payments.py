"""Tests for app.payments database helpers."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from contextlib import closing
from importlib import reload

import pytest

import database
import database.establish_db as establish_db
from app import payments


@pytest.fixture()
def isolated_payments_db(tmp_path, monkeypatch):
    db_path = tmp_path / "payments.db"
    monkeypatch.setattr(establish_db, "DATABASE", str(db_path))
    monkeypatch.setattr(database, "DATABASE", str(db_path))

    establish_db.ensure_schema()
    reload(payments)

    yield db_path


def _create_user() -> int:
    with establish_db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO user (username, password_hash, hash_algorithm, salt, phone_number)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("akhilesh", b"hash", "argon2id", b"salt", "5551234567"),
        )
        conn.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to retrieve inserted user id.")
        return int(lastrowid)


def _create_location_with_spot(*, spot_id: str = "A-101", hourly_cost_cents: int = 450) -> int:
    with establish_db.get_connection() as conn:
        location_cursor = conn.execute(
            """
            INSERT INTO location (lot_name, manager, manager_contact, hourly_cost_cents, x_coordinate, y_coordinate, data_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("Garage A", None, None, hourly_cost_cents, 0, 0, "lot1"),
        )
        location_id = location_cursor.lastrowid
        if location_id is None:
            raise RuntimeError("Failed to retrieve inserted location id.")

        conn.execute(
            """
            INSERT INTO parking_spot (
                location_id, spot_id, active, location_description, type,
                box_x_min, box_x_max, box_y_min, box_y_max
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (int(location_id), spot_id, True, "", "standard", 0, 1, 0, 1),
        )
        conn.commit()
        return int(location_id)


def test_create_parking_session_and_fee_use_default_timestamps(isolated_payments_db):
    user_id = _create_user()
    location_id = _create_location_with_spot(spot_id="A-101", hourly_cost_cents=450)

    session_id = payments.create_parking_session(user_id, "A-101", location_id)
    fee_id = payments.create_fee(user_id, "Parking", 9.0, session_id=session_id, valid_for_hours=Decimal("2"))

    with closing(sqlite3.connect(isolated_payments_db)) as conn:
        conn.row_factory = sqlite3.Row
        session_row = conn.execute(
            "SELECT user_id, location_id, spot_id, status, ended_at, started_at FROM parking_session WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        fee_row = conn.execute(
            "SELECT user_id, session_id, description, amount, fee_type, valid_until, created_at FROM fee WHERE fee_id = ?",
            (fee_id,),
        ).fetchone()

    assert session_row is not None
    assert session_row["user_id"] == user_id
    assert session_row["location_id"] == location_id
    assert session_row["spot_id"] == "A-101"
    assert session_row["status"] == "ON_HOLD"
    assert session_row["ended_at"] is None
    assert session_row["started_at"]

    assert fee_row is not None
    assert fee_row["user_id"] == user_id
    assert fee_row["session_id"] == session_id
    assert fee_row["description"] == "Parking"
    assert fee_row["amount"] == 9.0
    assert fee_row["fee_type"] == "regular_session"
    assert fee_row["valid_until"] is not None
    assert fee_row["created_at"] is not None


def test_record_payment_and_page_data_queries(isolated_payments_db):
    user_id = _create_user()
    location_id = _create_location_with_spot(spot_id="A-101", hourly_cost_cents=450)
    session_id = payments.create_parking_session(
        user_id,
        "A-101",
        location_id,
        status="IN_SESSION",
    )
    unpaid_fee_id = payments.create_fee(
        user_id,
        "Parking for garage A",
        9.0,
        session_id=session_id,
        valid_for_hours=Decimal("2"),
    )
    paid_fee_id = payments.create_fee(
        user_id,
        "Overstay violation",
        25.0,
        session_id=session_id,
        valid_for_hours=Decimal("24"),
    )

    payment_id = payments.record_payment(
        fee_id=paid_fee_id,
        amount=25.0,
        method="CARD",
        paid_at=1234567,
    )

    payment_page = payments.get_payment_page_data(user_id)
    assert payment_page["total_due"] == 9.0

    outstanding_fees = payment_page["outstanding_fees"]
    assert len(outstanding_fees) == 1
    assert outstanding_fees[0].fee_id == unpaid_fee_id
    assert outstanding_fees[0].description == "Parking for garage A"

    transactions_page = payments.get_transactions_page_data(user_id)
    assert transactions_page["total_paid"] == 25.0

    transactions = transactions_page["transactions"]
    assert len(transactions) == 1
    assert transactions[0].payment_id == payment_id
    assert transactions[0].fee_id == paid_fee_id
    assert transactions[0].description == "Overstay violation"
    assert transactions[0].method == "CARD"


def test_getters_return_empty_lists_when_no_data(isolated_payments_db):
    user_id = _create_user()

    payment_page = payments.get_payment_page_data(user_id)
    transactions_page = payments.get_transactions_page_data(user_id)

    assert payment_page == {"outstanding_fees": [], "total_due": 0}
    assert transactions_page == {"transactions": [], "total_paid": 0}


def test_get_active_sessions_filters_ended_sessions(isolated_payments_db):
    user_id = _create_user()
    other_user_id = None

    with establish_db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user (username, password_hash, hash_algorithm, salt, phone_number)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("other_user", b"hash", "argon2id", b"salt", "5550000000"),
        )
        row = conn.execute(
            "SELECT user_id FROM user WHERE username = ?",
            ("other_user",),
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to create other_user test fixture.")
        other_user_id = int(row["user_id"])
        conn.commit()

    location_id = _create_location_with_spot(spot_id="A-101", hourly_cost_cents=450)
    with establish_db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO parking_spot (
                location_id, spot_id, active, location_description, type,
                box_x_min, box_x_max, box_y_min, box_y_max
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (location_id, "B-201", True, "", "standard", 2, 3, 2, 3),
        )
        conn.commit()

    active_session_id = payments.create_parking_session(
        user_id,
        "A-101",
        location_id,
        status="IN_SESSION",
    )
    payments.create_fee(
        user_id,
        "Parking reservation for A-101",
        9.0,
        session_id=active_session_id,
        valid_for_hours=Decimal("876000"),
    )
    completed_session_id = payments.create_parking_session(
        user_id,
        "B-201",
        location_id,
        status="COMPLETED",
    )
    with establish_db.get_connection() as conn:
        conn.execute(
            "UPDATE parking_session SET ended_at = ? WHERE session_id = ?",
            ("2026-04-19T11:00:00+00:00", completed_session_id),
        )
        conn.commit()
    payments.create_parking_session(
        other_user_id,
        "A-101",
        location_id,
        status="IN_SESSION",
    )

    active_sessions = payments.get_active_sessions(user_id)
    assert len(active_sessions) == 1
    assert active_sessions[0].session_id == active_session_id
    assert active_sessions[0].spot_id == "A-101"
    assert active_sessions[0].lot_name == "Garage A"
    assert active_sessions[0].status == "IN_SESSION"
    assert active_sessions[0].hourly_rate == 4.5
    assert active_sessions[0].time_remaining not in {"Unavailable", "Expired"}


def test_record_payment_rejects_unknown_fee(isolated_payments_db):
    with pytest.raises(ValueError, match="does not exist"):
        payments.record_payment(fee_id=999, amount=5.0, method="CARD")


def test_record_payment_rejects_underpayment(isolated_payments_db):
    user_id = _create_user()
    session_id = payments.create_parking_session(user_id, "A-101", _create_location_with_spot())
    fee_id = payments.create_fee(user_id, "Daily parking", 12.0, session_id=session_id, valid_for_hours=Decimal("2"))

    with pytest.raises(ValueError, match="full fee cost"):
        payments.record_payment(fee_id=fee_id, amount=10.0, method="CARD")


def test_create_parking_session_rejects_unknown_spot_location_mapping(isolated_payments_db):
    user_id = _create_user()

    with pytest.raises(ValueError, match="does not exist"):
        payments.create_parking_session(user_id, "A-404", location_id=999)


class _NullLastRowIdCursor:
    lastrowid = None


class _LookupCursor:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    def fetchone(self):
        return self._row


class _CreateOnlyConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, params: tuple[object, ...]):
        self.executed.append((sql, params))
        if "SELECT location.hourly_cost_cents" in sql:
            return _LookupCursor({"hourly_cost_cents": 500})
        return _NullLastRowIdCursor()

    def commit(self) -> None:
        return None


class _RecordPaymentConnection:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []

    def execute(self, sql: str, params: tuple[object, ...]):
        self.executed_sql.append(sql)
        if sql.startswith("SELECT amount AS due_amount FROM fee"):
            class _FeeRow:
                def __getitem__(self, key: str) -> float:
                    assert key == "due_amount"
                    return 12.0

            class _FeeCursor:
                def fetchone(self) -> _FeeRow | None:
                    return _FeeRow()

            return _FeeCursor()

        return _NullLastRowIdCursor()

    def commit(self) -> None:
        return None


class _ConnectionManager:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    def __enter__(self) -> object:
        return self._connection

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_create_parking_session_raises_when_lastrowid_missing(monkeypatch):
    monkeypatch.setattr(payments, "get_connection", lambda: _ConnectionManager(_CreateOnlyConnection()))

    with pytest.raises(RuntimeError, match="parking session"):
        payments.create_parking_session(1, "A-101", 1)


def test_get_spot_hourly_rate_raises_when_location_rate_missing(monkeypatch):
    class _MissingRateConnection:
        def execute(self, _sql: str, _params: tuple[object, ...]):
            return _LookupCursor({"hourly_cost_cents": None})

    monkeypatch.setattr(payments, "get_connection", lambda: _ConnectionManager(_MissingRateConnection()))

    with pytest.raises(ValueError, match="no hourly_cost_cents"):
        payments.get_spot_hourly_rate(location_id=1, spot_id="A-101")


def test_create_fee_raises_when_lastrowid_missing(monkeypatch):
    monkeypatch.setattr(payments, "get_connection", lambda: _ConnectionManager(_CreateOnlyConnection()))

    with pytest.raises(RuntimeError, match="create fee"):
        payments.create_fee(1, "Parking", 9.0, session_id=1, valid_for_hours=Decimal("2"))


def test_record_payment_raises_when_lastrowid_missing(monkeypatch):
    monkeypatch.setattr(payments, "get_connection", lambda: _ConnectionManager(_RecordPaymentConnection()))

    with pytest.raises(RuntimeError, match="record payment"):
        payments.record_payment(fee_id=1, amount=12.0, method="CARD")
