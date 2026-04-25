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


def create_parking_session(
    user_id: int,
    spot_id: str,
    hourly_rate: float,
    *,
    status: str = "ON_HOLD",
    started_at: str | None = None,
    ended_at: str | None = None,
) -> int:
    session_started_at = started_at or _utc_now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO parking_session (user_id, spot_id, status, started_at, ended_at, hourly_rate)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, spot_id, status, session_started_at, ended_at, hourly_rate),
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
    fee_created_at = created_at or _utc_now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO fee (user_id, session_id, description, cost, status, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, session_id, description, cost, status, valid_until, fee_created_at),
        )
        conn.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create fee: no row id returned.")
        return int(lastrowid)


def record_payment(fee_id: int, amount: float, method: str, *, paid_at: str | None = None) -> int:
    payment_paid_at = paid_at or _utc_now_iso()
    with get_connection() as conn:
        fee_row = conn.execute(
            "SELECT cost FROM fee WHERE fee_id = ?",
            (fee_id,),
        ).fetchone()
        if fee_row is None:
            raise ValueError(f"Fee {fee_id} does not exist.")

        fee_cost = float(fee_row["cost"])
        if amount < fee_cost:
            raise ValueError("Payment amount must cover the full fee cost.")

        cursor = conn.execute(
            """
            INSERT INTO payment (fee_id, method, amount, paid_at)
            VALUES (?, ?, ?, ?)
            """,
            (fee_id, method, amount, payment_paid_at),
        )
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
        rows = conn.execute(
            """
            SELECT fee_id, session_id, description, cost, status, valid_until, created_at
            FROM fee
            WHERE user_id = ? AND status != 'PAID'
            ORDER BY created_at DESC, fee_id DESC
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
