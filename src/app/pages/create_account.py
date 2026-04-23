"""Create account page and credential handling."""

from typing import Any

from flask import Blueprint, current_app, g, make_response, redirect, render_template_string, request, url_for
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


_CREATE_ACCOUNT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
	<meta charset="UTF-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1.0" />
	<title>Create Account</title>
	<style>
		body {
			margin: 0;
			min-height: 100vh;
			display: grid;
			place-items: center;
			font-family: "Segoe UI", sans-serif;
			background: linear-gradient(135deg, #f5f7fa 0%, #e4ecfb 100%);
		}
		.card {
			width: min(420px, 92vw);
			background: #fff;
			border-radius: 16px;
			padding: 28px;
			box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
		}
		h1 {
			margin: 0 0 10px;
			font-size: 1.6rem;
			color: #0f172a;
		}
		p {
			margin: 0 0 18px;
			color: #475569;
		}
		label {
			display: block;
			margin-bottom: 6px;
			font-weight: 600;
			color: #1e293b;
		}
		input {
			width: 100%;
			box-sizing: border-box;
			border: 1px solid #cbd5e1;
			border-radius: 10px;
			padding: 10px 12px;
			margin-bottom: 14px;
			font-size: 1rem;
		}
		input[type="submit"],
		button {
			width: 100%;
			border: 0;
			border-radius: 10px;
			background: #0f766e;
			color: #fff;
			padding: 12px;
			font-weight: 700;
			cursor: pointer;
		}
		.error {
			margin-bottom: 12px;
			color: #b91c1c;
			font-weight: 600;
		}
		.footer {
			margin-top: 16px;
			text-align: center;
			color: #475569;
		}
		.footer a {
			color: #0f766e;
			font-weight: 700;
			text-decoration: none;
		}
	</style>
</head>
<body>
	<main class="card">
		<h1>Create your account</h1>
		<p>Set up access to Parking Database.</p>

		{% if error_message %}
			<div class="error">{{ error_message }}</div>
		{% endif %}

		<form method="post" novalidate>
			{{ form.hidden_tag() }}
			<label for="username">Username</label>
			{{ form.username(id="username", autocomplete="username") }}

			<label for="phone_number">Phone Number</label>
			{{ form.phone_number(id="phone_number", autocomplete="tel") }}

			<label for="password">Password</label>
			{{ form.password(id="password", autocomplete="new-password") }}

			<label for="confirm_password">Confirm Password</label>
			{{ form.confirm_password(id="confirm_password", autocomplete="new-password") }}

			{{ form.submit(class_="submit") }}
		</form>

		<p class="footer">Already have an account? <a href="{{ url_for('login.login') }}">Sign in</a></p>
	</main>
</body>
</html>
"""


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

	return render_template_string(_CREATE_ACCOUNT_TEMPLATE, form=form, error_message=error_message)