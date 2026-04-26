"""Tests for app.payments database helpers."""

from __future__ import annotations

import sqlite3
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

    original_schema = list(establish_db.EXPECTED_SCHEMA)
    establish_db.EXPECTED_SCHEMA.clear()

    establish_db.register_table(
        establish_db.Table(
            name="user",
            columns=(
                establish_db.SQLColumn("user_id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                establish_db.SQLColumn("username", "TEXT NOT NULL UNIQUE"),
                establish_db.SQLColumn("password_hash", "BLOB NOT NULL"),
                establish_db.SQLColumn("hash_algorithm", "TEXT NOT NULL"),
                establish_db.SQLColumn("salt", "BLOB NOT NULL"),
                establish_db.SQLColumn("phone_number", "TEXT NOT NULL"),
            ),
        )
    )
    establish_db.register_table(
        establish_db.Table(
            name="location",
            columns=(
                establish_db.SQLColumn("location_id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                establish_db.SQLColumn("lot_name", "TEXT NOT NULL"),
                establish_db.SQLColumn("hourly_cost_cents", "INTEGER NOT NULL"),
            ),
        )
    )
    establish_db.register_table(
        establish_db.Table(
            name="parking_spot",
            columns=(
                establish_db.SQLColumn("location_id", "INTEGER NOT NULL"),
                establish_db.SQLColumn("spot_id", "TEXT NOT NULL"),
            ),
            primary_key=("location_id", "spot_id"),
            extra_constraints=(
                establish_db.SQLColumn(
                    "fk_spot_location",
                    "FOREIGN KEY (location_id) REFERENCES location(location_id)",
                ),
            ),
        )
    )
    establish_db.register_table(
        establish_db.Table(
            name="parking_session",
            columns=(
                establish_db.SQLColumn("session_id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                establish_db.SQLColumn("user_id", "INTEGER NOT NULL"),
                establish_db.SQLColumn("spot_id", "TEXT NOT NULL"),
                establish_db.SQLColumn("status", "TEXT NOT NULL"),
                establish_db.SQLColumn("started_at", "TEXT NOT NULL"),
                establish_db.SQLColumn("ended_at", "TEXT"),
            ),
            extra_constraints=(
                establish_db.SQLColumn(
                    "fk_parking_session_user",
                    "FOREIGN KEY (user_id) REFERENCES user(user_id)",
                ),
            ),
        )
    )
    establish_db.register_table(
        establish_db.Table(
            name="fee",
            columns=(
                establish_db.SQLColumn("fee_id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                establish_db.SQLColumn("user_id", "INTEGER NOT NULL"),
                establish_db.SQLColumn("session_id", "INTEGER"),
                establish_db.SQLColumn("description", "TEXT NOT NULL"),
                establish_db.SQLColumn("cost", "REAL NOT NULL"),
                establish_db.SQLColumn("status", "TEXT NOT NULL"),
                establish_db.SQLColumn("valid_until", "TEXT"),
                establish_db.SQLColumn("created_at", "TEXT NOT NULL"),
            ),
            extra_constraints=(
                establish_db.SQLColumn(
                    "fk_fee_user",
                    "FOREIGN KEY (user_id) REFERENCES user(user_id)",
                ),
                establish_db.SQLColumn(
                    "fk_fee_session",
                    "FOREIGN KEY (session_id) REFERENCES parking_session(session_id)",
                ),
            ),
        )
    )
    establish_db.register_table(
        establish_db.Table(
            name="payment",
            columns=(
                establish_db.SQLColumn("payment_id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                establish_db.SQLColumn("fee_id", "INTEGER NOT NULL"),
                establish_db.SQLColumn("method", "TEXT NOT NULL"),
                establish_db.SQLColumn("amount", "REAL NOT NULL"),
                establish_db.SQLColumn("paid_at", "TEXT NOT NULL"),
            ),
            extra_constraints=(
                establish_db.SQLColumn(
                    "fk_payment_fee",
                    "FOREIGN KEY (fee_id) REFERENCES fee(fee_id)",
                ),
            ),
        )
    )

    establish_db.ensure_schema()
    reload(payments)

    yield db_path

    establish_db.EXPECTED_SCHEMA.clear()
    establish_db.EXPECTED_SCHEMA.extend(original_schema)


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
            INSERT INTO location (lot_name, hourly_cost_cents)
            VALUES (?, ?)
            """,
            ("Garage A", hourly_cost_cents),
        )
        location_id = location_cursor.lastrowid
        if location_id is None:
            raise RuntimeError("Failed to retrieve inserted location id.")

        conn.execute(
            """
            INSERT INTO parking_spot (location_id, spot_id)
            VALUES (?, ?)
            """,
            (int(location_id), spot_id),
        )
        conn.commit()
        return int(location_id)


def test_create_parking_session_and_fee_use_default_timestamps(isolated_payments_db):
    user_id = _create_user()
    location_id = _create_location_with_spot(spot_id="A-101", hourly_cost_cents=450)

    session_id = payments.create_parking_session(user_id, "A-101", location_id)
    fee_id = payments.create_fee(user_id, "Parking", 9.0, session_id=session_id)

    with closing(sqlite3.connect(isolated_payments_db)) as conn:
        conn.row_factory = sqlite3.Row
        session_row = conn.execute(
            "SELECT user_id, spot_id, status, ended_at, started_at FROM parking_session WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        fee_row = conn.execute(
            "SELECT user_id, session_id, description, cost, status, valid_until, created_at FROM fee WHERE fee_id = ?",
            (fee_id,),
        ).fetchone()

    assert session_row is not None
    assert session_row["user_id"] == user_id
    assert session_row["spot_id"] == "A-101"
    assert session_row["status"] == "ON_HOLD"
    assert session_row["ended_at"] is None
    assert session_row["started_at"]

    assert fee_row is not None
    assert fee_row["user_id"] == user_id
    assert fee_row["session_id"] == session_id
    assert fee_row["description"] == "Parking"
    assert fee_row["cost"] == 9.0
    assert fee_row["status"] == "UNPAID"
    assert fee_row["valid_until"] is None
    assert fee_row["created_at"]


def test_record_payment_and_page_data_queries(isolated_payments_db):
    user_id = _create_user()
    location_id = _create_location_with_spot(spot_id="A-101", hourly_cost_cents=450)
    session_id = payments.create_parking_session(
        user_id,
        "A-101",
        location_id,
        status="IN_SESSION",
        started_at="2026-04-20T09:00:00+00:00",
    )
    unpaid_fee_id = payments.create_fee(
        user_id,
        "Parking for garage A",
        9.0,
        session_id=session_id,
        created_at="2026-04-20T10:00:00+00:00",
    )
    paid_fee_id = payments.create_fee(
        user_id,
        "Overstay violation",
        25.0,
        valid_until="2026-04-21T22:00:00+00:00",
        created_at="2026-04-20T11:00:00+00:00",
    )

    payment_id = payments.record_payment(
        fee_id=paid_fee_id,
        amount=25.0,
        method="CARD",
        paid_at="2026-04-20T11:30:00+00:00",
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


def test_record_payment_rejects_unknown_fee(isolated_payments_db):
    with pytest.raises(ValueError, match="does not exist"):
        payments.record_payment(fee_id=999, amount=5.0, method="CARD")


def test_record_payment_rejects_underpayment(isolated_payments_db):
    user_id = _create_user()
    fee_id = payments.create_fee(user_id, "Daily parking", 12.0)

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
        if sql.startswith("SELECT cost FROM fee"):
            class _FeeRow:
                def __getitem__(self, key: str) -> float:
                    assert key == "cost"
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
        payments.create_fee(1, "Parking", 9.0)


def test_record_payment_raises_when_lastrowid_missing(monkeypatch):
    monkeypatch.setattr(payments, "get_connection", lambda: _ConnectionManager(_RecordPaymentConnection()))

    with pytest.raises(RuntimeError, match="record payment"):
        payments.record_payment(fee_id=1, amount=12.0, method="CARD")
