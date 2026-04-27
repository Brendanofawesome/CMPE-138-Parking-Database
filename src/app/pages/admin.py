from __future__ import annotations

import time
from datetime import datetime

from flask import Blueprint, g, render_template, request

from ..payments import format_utc_timestamp

admin_bp = Blueprint("admin", __name__)


@admin_bp.app_template_filter("datetimeformat")
def datetimeformat(value):
    if value is None:
        return "N/A"

    try:
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M:%S")
        return str(value)
    except (ValueError, TypeError):
        return str(value)


@admin_bp.route("/admin/plate-check", methods=["GET", "POST"])
def plate_check_page():
    vehicle = None
    session = None
    fees = []
    message = None
    message_type = None
    issued_fee = None

    if request.method == "POST":
        plate_input = request.form.get("plate", "").strip().upper()
        plate_state = request.form.get("state", "").strip().upper()
        action = request.form.get("action", "check")

        db = g.current_db_conn

        vehicle = db.execute(
            """
            SELECT Licence_Value, Licence_State, make, color, model, user_id
            FROM vehicle
            WHERE Licence_Value = ? AND Licence_State = ?
            """,
            (plate_input, plate_state),
        ).fetchone()

        if vehicle is None:
            message = "No vehicle found for this plate."
            message_type = "error"
        else:
            session = db.execute(
                """
                SELECT
                    ps.session_id,
                    ps.user_id,
                    ps.spot_id,
                    ps.status,
                    ps.started_at,
                    ps.ended_at,
                    ps.Licence_Value,
                    ps.Licence_State,
                    COALESCE(l.hourly_cost_cents, 0) / 100.0 AS hourly_rate
                FROM parking_session AS ps
                LEFT JOIN location AS l
                    ON ps.location_id = l.location_id
                WHERE ps.Licence_Value = ?
                  AND ps.Licence_State = ?
                ORDER BY ps.session_id DESC
                LIMIT 1
                """,
                (plate_input, plate_state),
            ).fetchone()

            fees = db.execute(
                """
                SELECT
                    f.fee_id,
                    f.created_at,
                    f.valid_until,
                    f.amount,
                    f.description,
                    f.fee_type,
                    f.session_id,
                    CASE
                        WHEN p.payment_id IS NULL THEN 'UNPAID'
                        ELSE 'PAID'
                    END AS payment_status,
                    p.paid_at
                FROM fee f
                INNER JOIN parking_session ps
                    ON ps.session_id = f.session_id
                LEFT JOIN payment p ON p.fee_id = f.fee_id
                WHERE f.user_id = ?
                  AND ps.Licence_Value = ?
                  AND ps.Licence_State = ?
                ORDER BY f.created_at DESC, f.fee_id DESC
                """,
                (vehicle["user_id"], vehicle["Licence_Value"], vehicle["Licence_State"]),
            ).fetchall()
            
            if fees:
                fees = [
                    {
                        "fee_id": fee["fee_id"],
                        "created_at": fee["created_at"],
                        "valid_until": fee["valid_until"],
                        "amount": fee["amount"],
                        "description": fee["description"],
                        "fee_type": fee["fee_type"],
                        "session_id": fee["session_id"],
                        "payment_status": fee["payment_status"],
                        "paid_at": (
                            format_utc_timestamp(int(fee["paid_at"]))
                            if fee["paid_at"]
                            else "N/A")
                                    }
                    for fee in fees
                ]

            if action == "issue_ticket":
                if session is None:
                    message = "Cannot issue a violation: no parking session exists for this plate."
                    message_type = "warning"
                    return render_template(
                        "admin_plate_check.html",
                        vehicle=vehicle,
                        session=session,
                        fees=fees,
                        message=message,
                        message_type=message_type,
                        issued_fee=issued_fee,
                    )

                existing_violation = db.execute(
                    """
                    SELECT fee_id
                    FROM fee
                    WHERE user_id = ?
                      AND fee_type = 'violation'
                      AND (
                            session_id IS ? OR session_id = ?
                      )
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (
                        vehicle["user_id"],
                        session["session_id"] if session else None,
                        session["session_id"] if session else None,
                    ),
                ).fetchone()

                if existing_violation is not None:
                    message = "A violation already exists for this vehicle/session."
                    message_type = "warning"
                else:
                    now = int(time.time())
                    valid_until = now + (7 * 24 * 60 * 60)

                    ticket_cursor = db.execute(
                        """
                        INSERT INTO fee (
                            user_id,
                            parent_fee_id,
                            session_id,
                            created_at,
                            valid_until,
                            amount,
                            description,
                            fee_type
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            vehicle["user_id"],
                            None,
                            session["session_id"] if session else None,
                            now,
                            valid_until,
                            50.0,
                            "Manual admin-issued parking violation",
                            "violation",
                        ),
                    )
                    db.commit()

                    issued_fee_id = ticket_cursor.lastrowid

                    issued_fee = db.execute(
                        """
                        SELECT
                            f.fee_id,
                            f.created_at,
                            f.valid_until,
                            f.amount,
                            f.description,
                            f.fee_type,
                            f.session_id
                        FROM fee f
                        WHERE f.fee_id = ?
                        """,
                        (issued_fee_id,),
                    ).fetchone()

                    fees = db.execute(
                        """
                        SELECT
                            f.fee_id,
                            f.created_at,
                            f.valid_until,
                            f.amount,
                            f.description,
                            f.fee_type,
                            f.session_id,
                            CASE
                                WHEN p.payment_id IS NULL THEN 'UNPAID'
                                ELSE 'PAID'
                            END AS payment_status,
                            p.paid_at
                        FROM fee f
                        INNER JOIN parking_session ps
                            ON ps.session_id = f.session_id
                        LEFT JOIN payment p ON p.fee_id = f.fee_id
                        WHERE f.user_id = ?
                          AND ps.Licence_Value = ?
                          AND ps.Licence_State = ?
                        ORDER BY f.created_at DESC, f.fee_id DESC
                        """,
                        (
                            vehicle["user_id"],
                            vehicle["Licence_Value"],
                            vehicle["Licence_State"],
                        ),
                    ).fetchall()

                    message = "Violation ticket issued successfully."
                    message_type = "success"
            else:
                if session is not None:
                    message = f"Found vehicle and latest session for {plate_input} ({plate_state})."
                else:
                    message = f"Found vehicle for {plate_input} ({plate_state}), but no parking session exists yet."
                message_type = "success"

    return render_template(
        "admin_plate_check.html",
        vehicle=vehicle,
        session=session,
        fees=fees,
        message=message,
        message_type=message_type,
        issued_fee=issued_fee,
    )
