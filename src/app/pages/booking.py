from decimal import Decimal, InvalidOperation

from flask import Blueprint, request, jsonify, g, Response, url_for

from app.payments import create_fee, create_parking_session, get_spot_hourly_rate

booking_bp = Blueprint("booking", __name__)


def _parse_hours(hours_raw: object) -> Decimal:
    if hours_raw is None:
        raise ValueError("Missing hours.")

    try:
        hours = Decimal(str(hours_raw))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid hours.") from None

    if not hours.is_finite():
        raise ValueError("Invalid hours.")

    if hours < Decimal("1.0"):
        raise ValueError("Hours must be at least 1.0.")

    if (hours * 2) != (hours * 2).to_integral_value():
        raise ValueError("Hours must be in 0.5-hour increments.")

    return hours

@booking_bp.route("/book-spot", methods=["POST"])
def book_spot() -> Response:
    if g.current_user is None:
        response = jsonify({"error": "You must be logged in to book a spot."})
        response.status_code = 401
        return response

    data = request.get_json()
    spot_id = data.get("spot_id") if data else None
    location_id_raw = data.get("location_id") if data else None
    hours_raw = data.get("hours") if data else None

    if not spot_id:
        response = jsonify({"error": "Missing spot_id."})
        response.status_code = 400
        return response

    if location_id_raw is None:
        response = jsonify({"error": "Missing location_id."})
        response.status_code = 400
        return response

    try:
        location_id = int(location_id_raw)
    except (TypeError, ValueError):
        response = jsonify({"error": "Invalid location_id."})
        response.status_code = 400
        return response

    try:
        hours = _parse_hours(hours_raw)
    except ValueError as error:
        response = jsonify({"error": str(error)})
        response.status_code = 400
        return response

    user_id = g.current_user["user_id"]

    try:
        session_id = create_parking_session(
            user_id=user_id,
            spot_id=spot_id,
            location_id=location_id
        )
        hourly_rate = get_spot_hourly_rate(location_id=location_id, spot_id=spot_id)
    except ValueError as error:
        response = jsonify({"error": str(error)})
        response.status_code = 400
        return response

    computed_cost = float((Decimal(str(hourly_rate)) * hours).quantize(Decimal("0.01")))

    fee_id = create_fee(
        user_id=user_id,
        session_id=session_id,
        description=f"Normal Reservation",
        cost=computed_cost,
        valid_for_hours=hours
    )

    return jsonify({
        "message": "Spot booked successfully.",
        "session_id": session_id,
        "spot_id": spot_id,
        "location_id": location_id,
        "hours": float(hours),
        "cost": computed_cost,
        "fee_id": fee_id,
        "payments_url": url_for("payments.payments_page"),
    })
