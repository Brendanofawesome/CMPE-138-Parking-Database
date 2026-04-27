from __future__ import annotations

from flask import Blueprint, g, render_template

statistics_bp = Blueprint("statistics", __name__)


@statistics_bp.route("/admin/statistics", methods=["GET"])
def statistics_page():
    db = g.current_db_conn

    summary = db.execute(
        """
        SELECT
            COUNT(DISTINCT l.location_id) AS total_locations,
            COUNT(ps.spot_id) AS total_spots,
            SUM(CASE WHEN ps.active = 1 THEN 1 ELSE 0 END) AS active_spots,
            SUM(CASE WHEN ps.active = 0 THEN 1 ELSE 0 END) AS inactive_spots
        FROM location l
        LEFT JOIN parking_spot ps
            ON l.location_id = ps.location_id
        """
    ).fetchone()

    locations = db.execute(
        """
        SELECT
            l.location_id,
            l.lot_name,
            l.hourly_cost_cents,
            l.manager_contact,
            COUNT(ps.spot_id) AS total_spots,
            SUM(CASE WHEN ps.active = 1 THEN 1 ELSE 0 END) AS active_spots,
            SUM(CASE WHEN ps.active = 0 THEN 1 ELSE 0 END) AS inactive_spots
        FROM location l
        LEFT JOIN parking_spot ps
            ON l.location_id = ps.location_id
        GROUP BY l.location_id, l.lot_name, l.hourly_cost_cents, l.manager_contact
        ORDER BY l.location_id
        """
    ).fetchall()

    return render_template(
        "admin_statistics.html",
        summary=summary,
        locations=locations,
    )
