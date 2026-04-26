from __future__ import annotations

import time
from datetime import datetime

from flask import Blueprint, g, render_template, request

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
            SELECT Licence_Value, Licence_State, Make, Color, Model, user_id
            FROM vehicle
            WHERE Licence_Value = ? AND Licence_State = ?
            """,
            (plate_input, plate_state),
        ).fetchone()

        if vehicle is None:
            message = "No vehicle found for this plate."
            message_type = "error"
        else:
            # NOTE:
            # parking_session is keyed by user_id, not directly by vehicle,
            # so we fetch the latest session for the vehicle owner's account.
            session = db.execute(
                """
                SELECT session_id, user_id, spot_id, status, started_at, ended_at, hourly_rate
                FROM parking_session
                WHERE user_id = ?
                ORDER BY session_id DESC
                LIMIT 1
                """,
                (vehicle["user_id"],),
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
                LEFT JOIN payment p ON p.fee_id = f.fee_id
                WHERE f.Licence_Value = ? AND f.Licence_State = ? AND f.user_id = ?
                ORDER BY f.created_at DESC, f.fee_id DESC
                """,
                (vehicle["Licence_Value"], vehicle["Licence_State"], vehicle["user_id"]),
            ).fetchall()

            if action == "issue_ticket":
                existing_violation = db.execute(
                    """
                    SELECT fee_id
                    FROM fee
                    WHERE Licence_Value = ?
                      AND Licence_State = ?
                      AND user_id = ?
                      AND fee_type = 'violation'
                      AND (
                            session_id IS ? OR session_id = ?
                      )
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (
                        vehicle["Licence_Value"],
                        vehicle["Licence_State"],
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

                    db.execute(
                        """
                        INSERT INTO fee (
                            Licence_Value,
                            Licence_State,
                            user_id,
                            parent_fee_id,
                            session_id,
                            created_at,
                            valid_until,
                            amount,
                            description,
                            fee_type
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            vehicle["Licence_Value"],
                            vehicle["Licence_State"],
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
                        WHERE f.Licence_Value = ?
                          AND f.Licence_State = ?
                          AND f.user_id = ?
                        ORDER BY f.fee_id DESC
                        LIMIT 1
                        """,
                        (
                            vehicle["Licence_Value"],
                            vehicle["Licence_State"],
                            vehicle["user_id"],
                        ),
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
                        LEFT JOIN payment p ON p.fee_id = f.fee_id
                        WHERE f.Licence_Value = ? AND f.Licence_State = ? AND f.user_id = ?
                        ORDER BY f.created_at DESC, f.fee_id DESC
                        """,
                        (
                            vehicle["Licence_Value"],
                            vehicle["Licence_State"],
                            vehicle["user_id"],
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
