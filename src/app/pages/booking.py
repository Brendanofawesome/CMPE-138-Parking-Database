from decimal import Decimal, InvalidOperation

from flask import Blueprint, request, jsonify, g, Response, url_for

from sqlite3 import Connection

from app.payments import create_fee, create_parking_session, ensure_user_vehicle, get_spot_hourly_rate

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


def _parse_licence_field(value_raw: object, field_name: str) -> str:
    if value_raw is None:
        raise ValueError(f"Missing {field_name}.")

    value = str(value_raw).strip().upper()
    if not value:
        raise ValueError(f"Missing {field_name}.")

    return value

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
    licence_value_raw = data.get("licence_value") if data else None
    licence_state_raw = data.get("licence_state") if data else None
    
    db_connection: Connection = g.current_db_conn

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

    try:
        licence_value = _parse_licence_field(licence_value_raw, "licence_value")
        licence_state = _parse_licence_field(licence_state_raw, "licence_state")
    except ValueError as error:
        response = jsonify({"error": str(error)})
        response.status_code = 400
        return response

    user_id = g.current_user["user_id"]

    try:
        ensure_user_vehicle(
            user_id=user_id,
            licence_value=licence_value,
            licence_state=licence_state,
        )
        
        hourly_rate = get_spot_hourly_rate(location_id=location_id, spot_id=spot_id)
        computed_cost = float((Decimal(str(hourly_rate)) * hours).quantize(Decimal("0.01")))
        
        #enter sql transaction to ensure that session and fee are created atomically
        db_connection.execute("BEGIN")
        
        session_id = create_parking_session(
                conn=db_connection,
                user_id=user_id,
                spot_id=spot_id,
                location_id=location_id,
                licence_value=licence_value,
                licence_state=licence_state,
            )

        fee_id = create_fee(
            conn=db_connection,
            user_id=user_id,
            session_id=session_id,
            description="Normal Reservation",
            cost=computed_cost,
            valid_for_hours=hours
        )
        #exit sql transaction
        db_connection.execute("COMMIT")
        
    except ValueError as error:
        #rollback the transaction
        db_connection.execute("ROLLBACK")
        
        response = jsonify({"error": str(error)})
        response.status_code = 400
        return response
        

    return jsonify({
        "message": "Spot booked successfully.",
        "session_id": session_id,
        "spot_id": spot_id,
        "location_id": location_id,
        "licence_value": licence_value,
        "licence_state": licence_state,
        "hours": float(hours),
        "cost": computed_cost,
        "fee_id": fee_id,
        "payments_url": url_for("payments.payments_page"),
    })
