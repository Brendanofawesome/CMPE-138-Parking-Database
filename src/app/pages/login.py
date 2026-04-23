"""Login page and credential handling."""

from typing import Any

from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length

from ..auth import SESSION_DURATION_SECONDS, authenticate_user, revoke_session

login_bp = Blueprint("login", __name__)


class LoginForm(FlaskForm):
	username = StringField(
		"Username",
		validators=[DataRequired(), Length(max=150)],
	)
	password = PasswordField(
		"Password",
		validators=[DataRequired(), Length(max=256)],
	)
	submit = SubmitField("Login")

@login_bp.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
	form: Any = LoginForm()
	error_message = ""

	if g.get("current_user") is not None:
		return redirect(url_for("home"))

	if form.validate_on_submit():
		db = g.get("current_db_conn")
		if db is None:
			db_getter = current_app.config.get("GET_DATABASE")
			if db_getter is None:
				raise RuntimeError("GET_DATABASE is not configured")
			db = db_getter()
			g.current_db_conn = db

		session_cookie = authenticate_user(db,
			form.username.data or "",
			(form.password.data or "").encode("utf-8"),
		)

		if session_cookie is not None:
			response = make_response(redirect(url_for("home")))
			session_cookie_name: str = "session_id"
			response.set_cookie(
				session_cookie_name,
				session_cookie,
				max_age=SESSION_DURATION_SECONDS,
				httponly=current_app.config.get("SESSION_COOKIE_HTTPONLY", True),
				samesite=current_app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
				secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
			)
			return response

		error_message = "Invalid username or password."
	elif request.method == "POST":
		error_message = "Please fill in both username and password."

	return render_template("login.html", form=form, error_message=error_message)


@login_bp.route("/logout", methods=["POST"])
def logout() -> ResponseReturnValue:
	db = g.get("current_db_conn")
	if db is None:
		db_getter = current_app.config.get("GET_DATABASE")
		if db_getter is None:
			raise RuntimeError("GET_DATABASE is not configured")
		db = db_getter()
		g.current_db_conn = db

	session_cookie_name: str = "session_id"
	revoke_session(db, request.cookies.get(session_cookie_name))

	response = make_response(redirect(url_for("home")))
	response.delete_cookie(
		session_cookie_name,
		httponly=current_app.config.get("SESSION_COOKIE_HTTPONLY", True),
		samesite=current_app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
		secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
	)
	return response

	