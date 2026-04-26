from __future__ import annotations
from datetime import datetime

import time

from flask import Blueprint, g, render_template, request

admin_bp = Blueprint("admin", __name__)

@admin_bp.app_template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

@admin_bp.route("/admin/plate-check", methods=["GET", "POST"])
def plate_check_page():
    vehicle = None
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
            fees = db.execute(
                """
                SELECT fee_id, created_at, valid_until, amount, description, fee_type
                FROM fee
                WHERE Licence_Value = ? AND Licence_State = ? AND user_id = ?
                ORDER BY created_at DESC
                """,
                (vehicle["Licence_Value"], vehicle["Licence_State"], vehicle["user_id"]),
            ).fetchall()

            if action == "issue_ticket":
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
                        None,
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
                    SELECT fee_id, created_at, valid_until, amount, description, fee_type
                    FROM fee
                    WHERE Licence_Value = ? AND Licence_State = ? AND user_id = ?
                    ORDER BY fee_id DESC
                    LIMIT 1
                    """,
                    (vehicle["Licence_Value"], vehicle["Licence_State"], vehicle["user_id"]),
                ).fetchone()

                fees = db.execute(
                    """
                    SELECT fee_id, created_at, valid_until, amount, description, fee_type
                    FROM fee
                    WHERE Licence_Value = ? AND Licence_State = ? AND user_id = ?
                    ORDER BY created_at DESC
                    """,
                    (vehicle["Licence_Value"], vehicle["Licence_State"], vehicle["user_id"]),
                ).fetchall()

                message = "Violation ticket issued successfully."
                message_type = "success"
            else:
                message = f"Found vehicle for {plate_input} ({plate_state})."
                message_type = "success"

    return render_template(
        "admin_plate_check.html",
        vehicle=vehicle,
        fees=fees,
        message=message,
        message_type=message_type,
        issued_fee=issued_fee,
    )
