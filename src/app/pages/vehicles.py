from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from app.vehicles import delete_vehicle, get_saved_vehicles, save_vehicle

vehicles_bp = Blueprint("vehicles", __name__)


@vehicles_bp.route("/vehicles", methods=["GET"])
def vehicles_page() -> ResponseReturnValue:
    current_user = g.get("current_user")
    if current_user is None:
        return redirect(url_for("login.login"))

    user_id = int(current_user["user_id"])
    return render_template(
        "vehicles.html",
        vehicles=get_saved_vehicles(user_id),
        save_error=request.args.get("save_error"),
        save_success=request.args.get("save_success"),
        delete_success=request.args.get("delete_success"),
    )


@vehicles_bp.route("/vehicles", methods=["POST"])
def create_vehicle() -> ResponseReturnValue:
    current_user = g.get("current_user")
    if current_user is None:
        return redirect(url_for("login.login"))

    user_id = int(current_user["user_id"])
    licence_value = request.form.get("licence_value", "")
    licence_state = request.form.get("licence_state", "")
    make = request.form.get("make", "")
    model = request.form.get("model", "")
    color = request.form.get("color", "")

    if not all([licence_value.strip(), licence_state.strip(), make.strip(), model.strip()]):
        return redirect(url_for("vehicles.vehicles_page", save_error="Please fill in all required vehicle fields."))

    created = save_vehicle(
        user_id=user_id,
        licence_value=licence_value,
        licence_state=licence_state,
        make=make,
        model=model,
        color=color,
    )
    if not created:
        return redirect(url_for("vehicles.vehicles_page", save_error="That license plate is already saved."))

    return redirect(url_for("vehicles.vehicles_page", save_success="Vehicle saved successfully."))


@vehicles_bp.route("/vehicles/delete", methods=["POST"])
def remove_vehicle() -> ResponseReturnValue:
    current_user = g.get("current_user")
    if current_user is None:
        return redirect(url_for("login.login"))

    user_id = int(current_user["user_id"])
    licence_value = request.form.get("licence_value", "")
    licence_state = request.form.get("licence_state", "")

    deleted = delete_vehicle(user_id, licence_value, licence_state)
    if not deleted:
        return redirect(url_for("vehicles.vehicles_page", save_error="Vehicle not found."))

    return redirect(url_for("vehicles.vehicles_page", delete_success="Vehicle removed."))
