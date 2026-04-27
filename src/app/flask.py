"""helper to create and configure the flask application"""

from __future__ import annotations

import os
import secrets
import sqlite3  # for typing and member functions
from typing import Callable

from flask import Flask, g, request
from flask_wtf.csrf import CSRFProtect

# import all the pages
from app.pages.admin import admin_bp
from app.pages.booking import booking_bp
from app.pages.create_account import create_account_bp
from app.pages.login import login_bp
from app.pages.map import map_bp
from app.pages.staff import staff_bp
from app.pages.statistics import statistics_bp
from app.pages.booking import booking_bp
from app.pages.payments import payments_bp
from app.pages.parking_sessions import parking_sessions_bp
from app.pages.vehicles import vehicles_bp

csrf: CSRFProtect = CSRFProtect()

from .auth import load_current_user

csrf: CSRFProtect = CSRFProtect()


# register all your pages here
def register_pages(app: Flask) -> None:
    app.register_blueprint(map_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(create_account_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(parking_sessions_bp)
    app.register_blueprint(vehicles_bp)


# runs when someone accesses a page
def get_db(app: Flask) -> sqlite3.Connection:
    db: sqlite3.Connection | None = g.get("current_db_conn")
    if db is None:
        db_geter = app.config.get("GET_DATABASE")
        if db_geter is None:
            raise RuntimeError("GET_DATABASE function not found in app config")
        db = db_geter()
        g.current_db_conn = db
    if not isinstance(db, sqlite3.Connection):
        raise RuntimeError("GET_DATABASE function did not return a sqlite3.Connection")
    return db


# runs when someone closes a page
def close_db(_exception: BaseException | None = None) -> None:
    db = g.pop("current_db_conn", None)
    if db is not None:
        db.close()


def create_app(get_connection: Callable[[], sqlite3.Connection]) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
        GET_DATABASE=get_connection,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        WTF_CSRF_TIME_LIMIT=None,
    )

    csrf.init_app(app)
    app.teardown_appcontext(close_db)  # close db on exit

    @app.before_request  # authenticate user before entering code
    def _prepare_request() -> None:
        db = get_db(app)
        session_cookie_name: str = "session_id"
        g.current_user = load_current_user(db, request.cookies.get(session_cookie_name))
        if g.current_user is not None:
            app.logger.debug("authenticated user %s from cookie", g.current_user["user_id"])

    register_pages(app)

    app.add_url_rule("/", endpoint="home", view_func=app.view_functions["map.map_page"])

    return app
