"""helper to create and configure the flask application"""


from __future__ import annotations

import os
import secrets
import sqlite3 #for typing and member functions
from typing import Callable

from flask import Flask, g, request
from flask_wtf.csrf import CSRFProtect

csrf: CSRFProtect = CSRFProtect()

from .auth import load_current_user

#register all your pages here
def register_pages(app: Flask) -> None:
    from app.pages.login import login_bp
    from app.pages.create_account import create_account_bp
    app.register_blueprint(login_bp)
    app.register_blueprint(create_account_bp)

#runs when someone accesses a page
def get_db() -> sqlite3.Connection:
    db = g.get("current_db_conn")
    if db is None:
        db_geter = g.get("GET_DATABASE")
        if db_geter is not None:
            db = db_geter()
            g.current_db_conn = db
    return db

#runs when someone closes a page
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
    app.teardown_appcontext(close_db)

    @app.before_request
    def _prepare_request() -> None:
        db = get_db()
        session_cookie_name: str = app.config.get('SESSION_COOKIE_NAME', 'session')
        g.current_user = load_current_user(db, request.cookies.get(session_cookie_name))
    
    register_pages(app)

    @app.route("/")
    def hello_world() -> str:
        return '<p>Hello, World! Visit <a href="/login">/login</a> to sign in.</p>'

    return app