"""Home page that renders the campus parking map with interactive overlays."""

from __future__ import annotations

from pathlib import Path

import sqlite3
from flask import Blueprint, current_app, g, render_template_string, send_file, url_for
from flask.typing import ResponseReturnValue

main_page_bp = Blueprint("main_page", __name__)


def _final_map_path() -> Path:
    return Path(__file__).resolve().parents[1] / "map" / "map_data" / "final_map.png"


_MAIN_PAGE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Parking Map</title>
    <style>
        :root {
            --bg-a: #f5f7fa;
            --bg-b: #e4ecfb;
            --panel: #ffffff;
            --text: #1f2937;
            --muted: #64748b;
            --line: #cbd5e1;
            --ev: rgba(30, 144, 255, 0.45);
            --regular: rgba(148, 163, 184, 0.45);
            --handicap: rgba(245, 158, 11, 0.45);
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            height: 100vh;
            font-family: "Segoe UI", sans-serif;
            background: linear-gradient(135deg, var(--bg-a) 0%, var(--bg-b) 100%);
            color: var(--text);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: var(--panel);
            border-bottom: 1px solid var(--line);
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);
            z-index: 2;
        }

        .topbar-title {
            margin: 0;
            font-size: 1.1rem;
            font-weight: 700;
        }

        .topbar-auth {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9rem;
            color: var(--muted);
        }

        .topbar-auth a {
            text-decoration: none;
            color: #0f766e;
            font-weight: 700;
            background: #ecfdf5;
            border: 1px solid #86efac;
            border-radius: 8px;
            padding: 6px 10px;
        }

        .topbar-auth a:hover {
            background: #d1fae5;
        }

        .topbar-auth .username {
            font-weight: 700;
            color: #0f172a;
        }

        .bottom-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: var(--panel);
            border-top: 1px solid var(--line);
            box-shadow: 0 -6px 20px rgba(15, 23, 42, 0.08);
            z-index: 2;
        }

        .bottom-title {
            margin: 0;
            font-size: 1.1rem;
            font-weight: 700;
        }

        .legend {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            font-size: 0.9rem;
            color: var(--muted);
        }

        .chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .swatch {
            width: 14px;
            height: 14px;
            border-radius: 4px;
            border: 1px solid rgba(0, 0, 0, 0.2);
        }

        .map-shell {
            flex: 1;
            padding: 0;
            min-height: 0;
        }

        .map-viewport {
            width: 100%;
            height: 100%;
            min-height: 0;
            border: 0;
            background: #dde3ea;
            border-radius: 0;
            overflow: hidden;
            position: relative;
            touch-action: none;
            cursor: grab;
        }

        .map-viewport.dragging {
            cursor: grabbing;
        }

        .map-content {
            position: absolute;
            left: 0;
            top: 0;
            transform-origin: 0 0;
            will-change: transform;
            user-select: none;
        }

        .map-image {
            display: block;
            max-width: none;
            pointer-events: none;
            user-select: none;
            -webkit-user-drag: none;
        }

        .spot-overlay {
            position: absolute;
            inset: 0;
            pointer-events: auto;
        }

        .spot {
            stroke-width: 2;
            pointer-events: auto;
            cursor: pointer;
        }

        .spot.ev {
            fill: var(--ev);
            stroke: rgba(30, 144, 255, 0.95);
        }

        .spot.regular {
            fill: var(--regular);
            stroke: rgba(71, 85, 105, 0.95);
        }

        .spot.handicap {
            fill: var(--handicap);
            stroke: rgba(217, 119, 6, 0.95);
        }

        .notice {
            position: absolute;
            left: 14px;
            bottom: 14px;
            background: rgba(17, 24, 39, 0.82);
            color: #f8fafc;
            font-size: 0.82rem;
            border-radius: 8px;
            padding: 7px 10px;
            pointer-events: none;
        }

        .spot-tooltip {
            position: absolute;
            transform: translate(12px, 12px);
            background: rgba(15, 23, 42, 0.92);
            color: #f8fafc;
            padding: 7px 10px;
            border-radius: 8px;
            font-size: 0.82rem;
            pointer-events: none;
            opacity: 0;
            transition: opacity 120ms ease;
            white-space: nowrap;
            z-index: 3;
        }

        @media (max-width: 700px) {
            .topbar,
            .bottom-bar {
                flex-direction: column;
                align-items: flex-start;
            }

            .topbar-auth {
                flex-wrap: wrap;
            }
        }
    </style>
</head>
<body>
    <header class="topbar">
        <p class="topbar-title">CMPE Parking</p>
        <nav class="topbar-auth" aria-label="Authentication">
            {% if is_logged_in %}
                <span class="username">Signed in as {{ username }}</span>
            {% else %}
                <a href="{{ url_for('login.login') }}">Login</a>
                <a href="{{ url_for('create_account.create_account') }}">Create Account</a>
            {% endif %}
        </nav>
    </header>

    <main class="map-shell">
        <section class="map-viewport" id="mapViewport" aria-label="Interactive parking map">
            <div class="map-content" id="mapContent">
                <img
                    id="mapImage"
                    class="map-image"
                    src="{{ map_url }}"
                    alt="Campus parking map"
                    draggable="false"
                />
                <svg id="spotOverlay" class="spot-overlay" aria-hidden="true"></svg>
            </div>
            <p class="notice">Scroll to zoom. Drag to pan.</p>
            <div id="spotTooltip" class="spot-tooltip" role="status" aria-live="polite"></div>
        </section>
    </main>

    <footer class="bottom-bar">
        <p class="bottom-title">Parking Map</p>
        <div class="legend" aria-label="Parking type legend">
            <span class="chip"><span class="swatch" style="background: var(--ev);"></span>EV</span>
            <span class="chip"><span class="swatch" style="background: var(--regular);"></span>Regular</span>
            <span class="chip"><span class="swatch" style="background: var(--handicap);"></span>Handicap</span>
        </div>
    </footer>

    <script>
        const spots = {{ spots | tojson }};
        const viewport = document.getElementById("mapViewport");
        const content = document.getElementById("mapContent");
        const image = document.getElementById("mapImage");
        const overlay = document.getElementById("spotOverlay");
        const tooltip = document.getElementById("spotTooltip");

        const state = {
            scale: 1,
            minScale: 0.6,
            maxScale: 5,
            tx: 0,
            ty: 0,
            dragging: false,
            dragStartX: 0,
            dragStartY: 0,
            dragInitialTx: 0,
            dragInitialTy: 0,
            mapWidth: 0,
            mapHeight: 0,
        };

        function normalizeSpotType(typeValue) {
            const raw = String(typeValue || "").toLowerCase();
            if (raw === "ev") {
                return "ev";
            }
            if (raw === "handicap") {
                return "handicap";
            }
            return "regular";
        }

        function buildOverlay() {
            overlay.innerHTML = "";
            for (const spot of spots) {
                const x = Number(spot.box_x_min);
                const y = Number(spot.box_y_min);
                const width = Number(spot.box_x_max) - Number(spot.box_x_min);
                const height = Number(spot.box_y_max) - Number(spot.box_y_min);

                const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                rect.setAttribute("x", String(x));
                rect.setAttribute("y", String(y));
                rect.setAttribute("width", String(Math.max(width, 1)));
                rect.setAttribute("height", String(Math.max(height, 1)));
                rect.setAttribute("class", "spot " + normalizeSpotType(spot.type));
                rect.dataset.spotId = String(spot.spot_id || "Unknown");
                rect.dataset.locationName = String(spot.location_name || "Unknown");

                rect.addEventListener("pointerenter", (event) => {
                    const target = event.currentTarget;
                    tooltip.textContent = `Spot ${target.dataset.spotId} | ${target.dataset.locationName}`;
                    tooltip.style.opacity = "1";
                });

                rect.addEventListener("pointermove", (event) => {
                    const rectBounds = viewport.getBoundingClientRect();
                    tooltip.style.left = `${event.clientX - rectBounds.left}px`;
                    tooltip.style.top = `${event.clientY - rectBounds.top}px`;
                });

                rect.addEventListener("pointerleave", () => {
                    tooltip.style.opacity = "0";
                });

                overlay.appendChild(rect);
            }
        }

        function clampTranslation(nextTx, nextTy, nextScale) {
            const viewWidth = viewport.clientWidth;
            const viewHeight = viewport.clientHeight;
            const scaledWidth = state.mapWidth * nextScale;
            const scaledHeight = state.mapHeight * nextScale;

            let minX;
            let maxX;
            if (scaledWidth <= viewWidth) {
                minX = (viewWidth - scaledWidth) / 2;
                maxX = minX;
            } else {
                minX = viewWidth - scaledWidth;
                maxX = 0;
            }

            let minY;
            let maxY;
            if (scaledHeight <= viewHeight) {
                minY = (viewHeight - scaledHeight) / 2;
                maxY = minY;
            } else {
                minY = viewHeight - scaledHeight;
                maxY = 0;
            }

            return {
                tx: Math.min(maxX, Math.max(minX, nextTx)),
                ty: Math.min(maxY, Math.max(minY, nextTy)),
            };
        }

        function renderTransform() {
            const clamped = clampTranslation(state.tx, state.ty, state.scale);
            state.tx = clamped.tx;
            state.ty = clamped.ty;
            content.style.transform = `translate(${state.tx}px, ${state.ty}px) scale(${state.scale})`;
        }

        function zoomAt(clientX, clientY, zoomFactor) {
            const rect = viewport.getBoundingClientRect();
            const x = clientX - rect.left;
            const y = clientY - rect.top;

            const oldScale = state.scale;
            const targetScale = Math.min(state.maxScale, Math.max(state.minScale, oldScale * zoomFactor));
            if (targetScale === oldScale) {
                return;
            }

            const mapX = (x - state.tx) / oldScale;
            const mapY = (y - state.ty) / oldScale;
            state.scale = targetScale;
            state.tx = x - mapX * state.scale;
            state.ty = y - mapY * state.scale;

            renderTransform();
        }

        function fitMapInitially() {
            if (state.mapWidth === 0 || state.mapHeight === 0) {
                return;
            }

            const scaleX = viewport.clientWidth / state.mapWidth;
            const scaleY = viewport.clientHeight / state.mapHeight;
            state.scale = Math.min(1, Math.max(state.minScale, Math.min(scaleX, scaleY)));
            state.tx = 0;
            state.ty = 0;
            renderTransform();
        }

        viewport.addEventListener("wheel", (event) => {
            event.preventDefault();
            const zoomFactor = event.deltaY < 0 ? 1.1 : 0.9;
            zoomAt(event.clientX, event.clientY, zoomFactor);
        }, { passive: false });

        viewport.addEventListener("pointerdown", (event) => {
            state.dragging = true;
            state.dragStartX = event.clientX;
            state.dragStartY = event.clientY;
            state.dragInitialTx = state.tx;
            state.dragInitialTy = state.ty;
            viewport.classList.add("dragging");
            viewport.setPointerCapture(event.pointerId);
        });

        viewport.addEventListener("pointermove", (event) => {
            if (!state.dragging) {
                return;
            }

            const dx = event.clientX - state.dragStartX;
            const dy = event.clientY - state.dragStartY;
            state.tx = state.dragInitialTx + dx;
            state.ty = state.dragInitialTy + dy;
            tooltip.style.opacity = "0";
            renderTransform();
        });

        function endDrag(event) {
            if (!state.dragging) {
                return;
            }
            state.dragging = false;
            viewport.classList.remove("dragging");
            if (viewport.hasPointerCapture(event.pointerId)) {
                viewport.releasePointerCapture(event.pointerId);
            }
        }

        viewport.addEventListener("pointerup", endDrag);
        viewport.addEventListener("pointercancel", endDrag);

        window.addEventListener("resize", renderTransform);

        image.addEventListener("load", () => {
            state.mapWidth = image.naturalWidth;
            state.mapHeight = image.naturalHeight;
            content.style.width = `${state.mapWidth}px`;
            content.style.height = `${state.mapHeight}px`;
            overlay.setAttribute("viewBox", `0 0 ${state.mapWidth} ${state.mapHeight}`);
            overlay.setAttribute("width", String(state.mapWidth));
            overlay.setAttribute("height", String(state.mapHeight));
            buildOverlay();
            fitMapInitially();
        });
    </script>
</body>
</html>
"""


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

    return render_template_string(
        _MAIN_PAGE_TEMPLATE,
        map_url=url_for("main_page.final_map_image"),
        spots=spots,
        username=username,
        is_logged_in=is_logged_in,
    )


@main_page_bp.route("/map/final-map")
def final_map_image() -> ResponseReturnValue:
    map_path = _final_map_path()
    return send_file(map_path, mimetype="image/png")