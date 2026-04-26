"""Parking sessions page for active user sessions."""

from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, url_for
from flask.typing import ResponseReturnValue

from app.payments import get_active_sessions_page_data

parking_sessions_bp = Blueprint("parking_sessions", __name__)


@parking_sessions_bp.route("/parking-sessions", methods=["GET"])
def parking_sessions_page() -> ResponseReturnValue:
    current_user = g.get("current_user")
    if current_user is None:
        return redirect(url_for("login.login"))

    user_id = int(current_user["user_id"])
    session_data = get_active_sessions_page_data(user_id)
    return render_template(
        "parking_sessions.html",
        active_sessions=session_data["active_sessions"],
    )
