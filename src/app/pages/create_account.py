"""Create account page and credential handling."""

from typing import Any

from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length

from ..auth import SESSION_DURATION_SECONDS, create_user

create_account_bp = Blueprint("create_account", __name__)


class CreateAccountForm(FlaskForm):
	username = StringField(
		"Username",
		validators=[DataRequired(), Length(max=150)],
	)
	phone_number = StringField(
		"Phone Number",
		validators=[DataRequired(), Length(max=50)],
	)
	password = PasswordField(
		"Password",
		validators=[DataRequired(), Length(max=256)],
	)
	confirm_password = PasswordField(
		"Confirm Password",
		validators=[DataRequired(), EqualTo("password", message="Passwords must match."), Length(max=256)],
	)
	submit = SubmitField("Create Account")


@create_account_bp.route("/create-account", methods=["GET", "POST"])
def create_account() -> ResponseReturnValue:
	form: Any = CreateAccountForm()
	error_message = ""

	if g.get("current_user") is not None:
		return redirect(url_for("main_page.main_page"))

	if form.validate_on_submit():
		db = g.get("current_db_conn")
		if db is None:
			db_getter = current_app.config.get("GET_DATABASE")
			if db_getter is None:
				raise RuntimeError("GET_DATABASE is not configured")
			db = db_getter()
			g.current_db_conn = db

		session_cookie = create_user(
			db,
			form.username.data or "",
			(form.password.data or "").encode("utf-8"),
			form.phone_number.data or "",
		)

		if session_cookie is not None:
			response = make_response(redirect(url_for("main_page.main_page")))
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

		error_message = "That username is already taken."
	elif request.method == "POST":
		error_message = "Please fill out all fields and make sure the passwords match."

	return render_template("create_account.html", form=form, error_message=error_message)