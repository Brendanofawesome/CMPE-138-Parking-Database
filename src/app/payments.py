from __future__ import annotations
from typing import TypedDict

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlite3 import Connection

from database.establish_db import get_connection


def _utc_now_iso() -> int:
    return int(datetime.now(timezone.utc).timestamp())

def format_utc_timestamp(seconds: int) -> str:
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

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


@dataclass(frozen=True, slots=True)
class ActiveParkingSession:
    session_id: int
    spot_id: str
    lot_name: str
    vehicle_label: str
    status: str
    started_at: str
    hourly_rate: float
    total_cost: float
    time_remaining: str


def _format_time_remaining(valid_until_ts: int | None) -> str:
    if valid_until_ts is None:
        return "Unavailable"

    now_seconds = int(datetime.now(timezone.utc).timestamp())
    remaining_seconds = valid_until_ts - now_seconds
    if remaining_seconds <= 0:
        return "Expired"

    days, day_remainder = divmod(remaining_seconds, 24 * 60 * 60)
    hours, hour_remainder = divmod(day_remainder, 60 * 60)
    minutes = max(hour_remainder // 60, 0)

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _resolve_spot_hourly_cost_cents(conn: Connection, location_id: int, spot_id: str) -> int:
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
    licence_value: str,
    licence_state: str,
    status: str | None = None
) -> int:
    session_started_at =  _utc_now_iso()
    with get_connection() as conn:
        _resolve_spot_hourly_cost_cents(conn, location_id, spot_id)
        cursor = conn.execute(
            """
            INSERT INTO parking_session (user_id, location_id, spot_id, Licence_Value, Licence_State, status, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, location_id, spot_id, licence_value.strip().upper(), licence_state.strip().upper(), status, session_started_at, None),
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
    session_id: int,
    valid_for_hours: Decimal,
) -> int:
    with get_connection() as conn:
        created_at = _utc_now_iso()
        valid_until = created_at + int(valid_for_hours * Decimal(60 * 60))
        cursor = conn.execute(
            """
            INSERT INTO fee (user_id, parent_fee_id, session_id, created_at, valid_until, amount, description, fee_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (0, user_id, None, session_id, created_at, valid_until, cost, description, "regular_session"),
        )
        conn.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create fee: no row id returned.")
        return int(lastrowid)


def record_payment(fee_id: int, amount: float, method: str, *, paid_at: int | None = None) -> int:
    payment_paid_at = paid_at or _utc_now_iso()
    with get_connection() as conn:
        fee_row = conn.execute(
            "SELECT amount AS due_amount FROM fee WHERE fee_id = ?",
            (fee_id,),
        ).fetchone()
        if fee_row is None:
            raise ValueError(f"Fee {fee_id} does not exist.")

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
        conn.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to record payment: no row id returned.")
        return int(lastrowid)


def get_outstanding_fees(user_id: int) -> list[OutstandingFee]:
    with get_connection() as conn:
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


def get_active_sessions(user_id: int) -> list[ActiveParkingSession]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ps.session_id,
                ps.spot_id,
                ps.status,
                ps.started_at,
                COALESCE(ps.Licence_Value || " (" || ps.Licence_State || ")", "Unknown Vehicle") AS vehicle_label,
                COALESCE(fee_total.total_amount, 0) AS amount,
                COALESCE(l.lot_name, 'Unknown Lot') AS lot_name,
                COALESCE(l.hourly_cost_cents, 0) / 100.0 AS hourly_rate,
                latest_fee.valid_until AS valid_until
            FROM parking_session ps
            LEFT JOIN location l 
                ON l.location_id = ps.location_id

            -- total fee per session
            LEFT JOIN (
                SELECT session_id, SUM(amount) AS total_amount
                FROM fee
                WHERE session_id IS NOT NULL
                GROUP BY session_id
            ) AS fee_total 
                ON fee_total.session_id = ps.session_id

            -- latest valid_until per session
            LEFT JOIN (
                SELECT session_id, MAX(valid_until) AS valid_until
                FROM fee
                WHERE session_id IS NOT NULL
                GROUP BY session_id
            ) AS latest_fee 
                ON latest_fee.session_id = ps.session_id

            WHERE ps.user_id = ?
                AND ps.ended_at IS NULL
            ORDER BY ps.started_at DESC, ps.session_id DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        ActiveParkingSession(
            session_id=int(row["session_id"]),
            spot_id=str(row["spot_id"]),
            lot_name=str(row["lot_name"]),
            vehicle_label=str(row["vehicle_label"]),
            status=str(row["status"]),
            started_at=format_utc_timestamp(int(row["started_at"])),
            hourly_rate=float(row["hourly_rate"]),
            total_cost=float(row["amount"]),  # now correct total
            time_remaining=_format_time_remaining(
                int(row["valid_until"]) if row["valid_until"] is not None else None
            ),
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


ActiveSessionList = TypedDict("ActiveSessionList", {"active_sessions": list[ActiveParkingSession]})
def get_active_sessions_page_data(user_id: int) -> ActiveSessionList:
    return {
        "active_sessions": get_active_sessions(user_id),
    }
