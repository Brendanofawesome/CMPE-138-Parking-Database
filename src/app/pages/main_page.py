"""Home page that renders the campus parking map with interactive overlays."""

from __future__ import annotations

from pathlib import Path

import sqlite3
from flask import Blueprint, current_app, g, render_template, send_file, url_for
from flask.typing import ResponseReturnValue

main_page_bp = Blueprint("main_page", __name__)


def _final_map_path() -> Path:
    return Path(__file__).resolve().parents[1] / "map" / "map_data" / "final_map.png"




@main_page_bp.route("/")
def main_page() -> ResponseReturnValue:
    db: sqlite3.Connection | None = g.get("current_db_conn")
    if db is None:
        db_getter = current_app.config.get("GET_DATABASE")
        if db_getter is not None:
            db = db_getter()
            g.current_db_conn = db

    spots: list[dict[str, int | str]] = []
    username = ""
    is_logged_in = False
    if db is not None:
        try:
            rows = db.execute(
                """
                SELECT parking_spot.spot_id,
                       parking_spot.type,
                       parking_spot.box_x_min,
                       parking_spot.box_x_max,
                       parking_spot.box_y_min,
                       parking_spot.box_y_max,
                       location.lot_name AS location_name
                FROM parking_spot
                JOIN location ON location.location_id = parking_spot.location_id
                WHERE parking_spot.active = 1
                """
            ).fetchall()
            spots = [
                {
                    "spot_id": row["spot_id"],
                    "type": row["type"],
                    "box_x_min": row["box_x_min"],
                    "box_x_max": row["box_x_max"],
                    "box_y_min": row["box_y_min"],
                    "box_y_max": row["box_y_max"],
                    "location_name": row["location_name"],
                }
                for row in rows
            ]

            current_user = g.get("current_user")
            if current_user is not None:
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

    return render_template(
        "main_page.html",
        map_url=url_for("main_page.final_map_image"),
        spots=spots,
        username=username,
        is_logged_in=is_logged_in,
    )


@main_page_bp.route("/map/final-map")
def final_map_image() -> ResponseReturnValue:
    map_path = _final_map_path()
    return send_file(map_path, mimetype="image/png")
