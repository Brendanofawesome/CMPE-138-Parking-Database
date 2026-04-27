"""Home page that renders the campus parking map with interactive overlays."""

from __future__ import annotations

from pathlib import Path

import sqlite3
from flask import Blueprint, current_app, g, render_template, send_file, url_for
from flask.typing import ResponseReturnValue

map_bp = Blueprint("map", __name__)


def _final_map_path() -> Path:
    return Path(__file__).resolve().parents[1] / "map" / "map_data" / "final_map.png"

@map_bp.route("/")
def map_page() -> ResponseReturnValue:
    db: sqlite3.Connection | None = g.get("current_db_conn")
    if db is None:
        db_getter = current_app.config.get("GET_DATABASE")
        if db_getter is not None:
            db = db_getter()
            g.current_db_conn = db

    spots: list[dict[str, int | str]] = []
    saved_vehicles: list[dict[str, str]] = []
    username = ""
    is_logged_in = False
    current_user = g.get("current_user")
    current_user_id = int(current_user["user_id"]) if current_user is not None else -1

    if db is not None:
        try:
            rows = db.execute(
                """
                SELECT  parking_spot.spot_id,
                        parking_spot.location_id,
                        parking_spot.type,
                        parking_spot.box_x_min,
                        parking_spot.box_x_max,
                        parking_spot.box_y_min,
                        parking_spot.box_y_max,
                        location.lot_name AS location_name,
                        CASE
                            WHEN active_sessions.active_session_spot_id IS NULL THEN 0
                            ELSE 1
                        END AS is_booked,
                        COALESCE(active_sessions.is_booked_by_current_user, 0) AS is_booked_by_current_user
                FROM parking_spot
                JOIN location ON location.location_id = parking_spot.location_id
                LEFT JOIN (
                    SELECT
                        location_id AS active_session_location_id,
                        spot_id AS active_session_spot_id,
                        MAX(CASE WHEN user_id = ? THEN 1 ELSE 0 END) AS is_booked_by_current_user
                    FROM parking_session
                    WHERE ended_at IS NULL
                    GROUP BY location_id, spot_id
                ) AS active_sessions
                ON active_sessions.active_session_location_id = parking_spot.location_id
                AND active_sessions.active_session_spot_id = parking_spot.spot_id
                WHERE parking_spot.active = 1
                """,
                (current_user_id,),
            ).fetchall()
            
            spots = [
                {
                    "spot_id": row["spot_id"],
                    "location_id": row["location_id"],
                    "type": row["type"],
                    "box_x_min": row["box_x_min"],
                    "box_x_max": row["box_x_max"],
                    "box_y_min": row["box_y_min"],
                    "box_y_max": row["box_y_max"],
                    "location_name": row["location_name"],
                    "is_booked": bool(row["is_booked"]),
                    "is_booked_by_current_user": bool(row["is_booked_by_current_user"]),
                }
                for row in rows
            ]

            if current_user is not None:
                vehicle_rows = db.execute(
                    """
                    SELECT Licence_Value, Licence_State, make, model
                    FROM vehicle
                    WHERE user_id = ?
                    ORDER BY Licence_State, Licence_Value
                    """,
                    (current_user["user_id"],),
                ).fetchall()
                saved_vehicles = [
                    {
                        "license_value": str(row["Licence_Value"]),
                        "license_state": str(row["Licence_State"]),
                        "make": str(row["make"]),
                        "model": str(row["model"]),
                        "color": str(row["color"] or ""),
                    }
                    for row in vehicle_rows
                ]

                user_row = db.execute(
                    "SELECT username FROM user WHERE user_id = ?",
                    (current_user["user_id"],),
                ).fetchone()
                if user_row is not None:
                    username = str(user_row["username"])
                    is_logged_in = True
        except sqlite3.OperationalError:
            spots = []
            username = ""
            is_logged_in = False
            saved_vehicles = []

    return render_template(
        "map.html",
        map_url=url_for("map.final_map_image"),
        spots=spots,
        username=username,
        is_logged_in=is_logged_in,
        saved_vehicles=saved_vehicles,
    )


@map_bp.route("/map/final-map")
def final_map_image() -> ResponseReturnValue:
    map_path = _final_map_path()
    return send_file(map_path, mimetype="image/png")
