from importlib import reload

import database
import database.establish_db as establish_db
from database import payments


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
        return int(cursor.lastrowid)


def test_payment_schema_modules_register_tables(isolated_db_schema):
    reload(database)
    establish_db.ensure_schema()

    with establish_db.get_connection() as conn:
        table_names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            ).fetchall()
        }

    assert {"parking_session", "fee", "payment"}.issubset(table_names)


def test_payment_page_and_transactions_queries(isolated_db_schema):
    reload(database)
    establish_db.ensure_schema()
    user_id = _create_user()

    session_id = payments.create_parking_session(
        user_id=user_id,
        spot_id="A-101",
        hourly_rate=4.50,
        status="IN_SESSION",
        started_at="2026-04-20T09:00:00+00:00",
    )
    unpaid_fee_id = payments.create_fee(
        user_id=user_id,
        session_id=session_id,
        description="Parking for garage A",
        cost=9.00,
        created_at="2026-04-20T10:00:00+00:00",
    )
    paid_fee_id = payments.create_fee(
        user_id=user_id,
        description="Overstay violation",
        cost=25.00,
        valid_until="2026-04-21T22:00:00+00:00",
        created_at="2026-04-20T11:00:00+00:00",
    )

    payment_id = payments.record_payment(
        fee_id=paid_fee_id,
        amount=25.00,
        method="CARD",
        paid_at="2026-04-20T11:30:00+00:00",
    )

    payment_page = payments.get_payment_page_data(user_id)
    assert payment_page["total_due"] == 9.00

    outstanding_fees = payment_page["outstanding_fees"]
    assert len(outstanding_fees) == 1
    assert outstanding_fees[0].fee_id == unpaid_fee_id
    assert outstanding_fees[0].description == "Parking for garage A"

    transactions_page = payments.get_transactions_page_data(user_id)
    assert transactions_page["total_paid"] == 25.00

    transactions = transactions_page["transactions"]
    assert len(transactions) == 1
    assert transactions[0].payment_id == payment_id
    assert transactions[0].fee_id == paid_fee_id
    assert transactions[0].description == "Overstay violation"
    assert transactions[0].method == "CARD"


def test_record_payment_rejects_underpayment(isolated_db_schema):
    reload(database)
    establish_db.ensure_schema()
    user_id = _create_user()
    fee_id = payments.create_fee(
        user_id=user_id,
        description="Daily parking",
        cost=12.00,
    )

    try:
        payments.record_payment(fee_id=fee_id, amount=10.00, method="CARD")
    except ValueError as exc:
        assert "full fee cost" in str(exc)
    else:
        raise AssertionError("Expected underpayment to be rejected.")
