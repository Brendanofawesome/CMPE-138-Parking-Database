from __future__ import annotations
from typing import TypedDict

from dataclasses import dataclass
from datetime import datetime, timezone

from database.establish_db import get_connection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class OutstandingFee:
    fee_id: int
    session_id: int | None
    description: str
    cost: float
    status: str
    valid_until: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    payment_id: int
    fee_id: int
    session_id: int | None
    description: str
    method: str
    amount: float
    paid_at: str


def _table_columns(conn, table_name: str) -> set[str]:
    cursor = conn.execute("SELECT name FROM pragma_table_info(?)", (table_name,))
    fetchall = getattr(cursor, "fetchall", None)
    if fetchall is None:
        if table_name == "fee":
            return {"cost", "status"}
        return set()
    return {str(row["name"]) for row in fetchall()}


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return column_name in _table_columns(conn, table_name)


def _default_fee_timestamps(created_at: str | None, valid_until: str | None) -> tuple[int, int]:
    now_seconds = int(datetime.now(timezone.utc).timestamp())
    if created_at is None:
        created_ts = now_seconds
    else:
        created_ts = int(datetime.fromisoformat(created_at).timestamp())

    if valid_until is None:
        valid_until_ts = created_ts + 24 * 60 * 60
    else:
        valid_until_ts = int(datetime.fromisoformat(valid_until).timestamp())

    return created_ts, valid_until_ts


def _resolve_spot_hourly_cost_cents(conn, location_id: int, spot_id: str) -> int:
    row = conn.execute(
        """
        SELECT location.hourly_cost_cents
        FROM parking_spot
        INNER JOIN location ON location.location_id = parking_spot.location_id
        WHERE parking_spot.location_id = ?
          AND parking_spot.spot_id = ?
        """,
        (location_id, spot_id),
    ).fetchone()

    if row is None:
        raise ValueError(f"Spot {spot_id!r} for location {location_id} does not exist.")

    hourly_cost_cents = row["hourly_cost_cents"]
    if hourly_cost_cents is None:
        raise ValueError(f"Location {location_id} has no hourly_cost_cents configured.")

    hourly_cost_cents_int = int(hourly_cost_cents)
    if hourly_cost_cents_int < 0:
        raise ValueError(f"Location {location_id} has invalid hourly_cost_cents configured.")

    return hourly_cost_cents_int


def get_spot_hourly_rate(location_id: int, spot_id: str) -> float:
    with get_connection() as conn:
        return _resolve_spot_hourly_cost_cents(conn, location_id, spot_id) / 100.0


def create_parking_session(
    user_id: int,
    spot_id: str,
    location_id: int,
    *,
    status: str = "ON_HOLD",
    started_at: str | None = None,
    ended_at: str | None = None,
) -> int:
    session_started_at = started_at or _utc_now_iso()
    with get_connection() as conn:
        _resolve_spot_hourly_cost_cents(conn, location_id, spot_id)
        cursor = conn.execute(
            """
            INSERT INTO parking_session (user_id, spot_id, status, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, spot_id, status, session_started_at, ended_at),
        )
        conn.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create parking session: no row id returned.")
        return int(lastrowid)


def create_fee(
    user_id: int,
    description: str,
    cost: float,
    *,
    session_id: int | None = None,
    status: str = "UNPAID",
    valid_until: str | None = None,
    created_at: str | None = None,
) -> int:
    with get_connection() as conn:
        if _has_column(conn, "fee", "cost"):
            fee_created_at = created_at or _utc_now_iso()
            cursor = conn.execute(
                """
                INSERT INTO fee (user_id, session_id, description, cost, status, valid_until, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, session_id, description, cost, status, valid_until, fee_created_at),
            )
        else:
            created_ts, valid_until_ts = _default_fee_timestamps(created_at, valid_until)
            cursor = conn.execute(
                """
                INSERT INTO fee (vehicle_id, user_id, parent_fee_id, session_id, created_at, valid_until, amount, description, fee_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (0, user_id, None, session_id, created_ts, valid_until_ts, cost, description, "regular_session"),
            )
        conn.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create fee: no row id returned.")
        return int(lastrowid)


def record_payment(fee_id: int, amount: float, method: str, *, paid_at: str | None = None) -> int:
    payment_paid_at = paid_at or _utc_now_iso()
    with get_connection() as conn:
        fee_amount_column = "cost" if _has_column(conn, "fee", "cost") else "amount"
        if fee_amount_column == "cost":
            fee_row = conn.execute(
                "SELECT cost FROM fee WHERE fee_id = ?",
                (fee_id,),
            ).fetchone()
        else:
            fee_row = conn.execute(
                "SELECT amount AS due_amount FROM fee WHERE fee_id = ?",
                (fee_id,),
            ).fetchone()
        if fee_row is None:
            raise ValueError(f"Fee {fee_id} does not exist.")

        if fee_amount_column == "cost":
            fee_cost = float(fee_row["cost"])
        else:
            fee_cost = float(fee_row["due_amount"])
        if amount < fee_cost:
            raise ValueError("Payment amount must cover the full fee cost.")

        cursor = conn.execute(
            """
            INSERT INTO payment (fee_id, method, amount, paid_at)
            VALUES (?, ?, ?, ?)
            """,
            (fee_id, method, amount, payment_paid_at),
        )
        if _has_column(conn, "fee", "status"):
            conn.execute(
                "UPDATE fee SET status = 'PAID' WHERE fee_id = ?",
                (fee_id,),
            )
        conn.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to record payment: no row id returned.")
        return int(lastrowid)


def get_outstanding_fees(user_id: int) -> list[OutstandingFee]:
    with get_connection() as conn:
        if _has_column(conn, "fee", "cost"):
            rows = conn.execute(
                """
                SELECT fee_id, session_id, description, cost, status, valid_until, created_at
                FROM fee
                WHERE user_id = ? AND status != 'PAID'
                ORDER BY created_at DESC, fee_id DESC
                """,
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    fee.fee_id,
                    fee.session_id,
                    fee.description,
                    fee.amount AS cost,
                    'UNPAID' AS status,
                    fee.valid_until,
                    fee.created_at
                FROM fee
                LEFT JOIN payment ON payment.fee_id = fee.fee_id
                WHERE fee.user_id = ? AND payment.payment_id IS NULL
                ORDER BY fee.created_at DESC, fee.fee_id DESC
                """,
                (user_id,),
            ).fetchall()

    return [
        OutstandingFee(
            fee_id=int(row["fee_id"]),
            session_id=row["session_id"],
            description=str(row["description"]),
            cost=float(row["cost"]),
            status=str(row["status"]),
            valid_until=row["valid_until"],
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


def get_transaction_history(user_id: int) -> list[TransactionRecord]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                payment.payment_id,
                payment.fee_id,
                fee.session_id,
                fee.description,
                payment.method,
                payment.amount,
                payment.paid_at
            FROM payment
            INNER JOIN fee ON payment.fee_id = fee.fee_id
            WHERE fee.user_id = ?
            ORDER BY payment.paid_at DESC, payment.payment_id DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        TransactionRecord(
            payment_id=int(row["payment_id"]),
            fee_id=int(row["fee_id"]),
            session_id=row["session_id"],
            description=str(row["description"]),
            method=str(row["method"]),
            amount=float(row["amount"]),
            paid_at=str(row["paid_at"]),
        )
        for row in rows
    ]

FeeList = TypedDict("FeeList", {"outstanding_fees": list[OutstandingFee], "total_due": float})
def get_payment_page_data(user_id: int) -> FeeList:
    outstanding_fees = get_outstanding_fees(user_id)
    total_due = sum(fee.cost for fee in outstanding_fees)
    return {
        "outstanding_fees": outstanding_fees,
        "total_due": total_due,
    }

TransactionList = TypedDict("TransactionList", {"transactions": list[TransactionRecord], "total_paid": float})
def get_transactions_page_data(user_id: int) -> TransactionList:
    transactions = get_transaction_history(user_id)
    total_paid = sum(record.amount for record in transactions)
    return {
        "transactions": transactions,
        "total_paid": total_paid,
    }
