from __future__ import annotations

from flask import Blueprint, g, render_template

staff_bp = Blueprint("staff", __name__)


@staff_bp.route("/admin/staff", methods=["GET"])
def staff_page():
    db = g.current_db_conn

    users = db.execute(
        """
        SELECT user_id, username, phone_number
        FROM user
        ORDER BY user_id
        """
    ).fetchall()

    return render_template(
        "admin_staff.html",
        users=users,
    )
