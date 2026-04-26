from flask import Blueprint, request, jsonify, g, Response, url_for

from app.payments import create_fee, create_parking_session

booking_bp = Blueprint("booking", __name__)

@booking_bp.route("/book-spot", methods=["POST"])
def book_spot() -> Response:
    if g.current_user is None:
        response = jsonify({"error": "You must be logged in to book a spot."})
        response.status_code = 401
        return response

    data = request.get_json()
    spot_id = data.get("spot_id") if data else None

    if not spot_id:
        response = jsonify({"error": "Missing spot_id."})
        response.status_code = 400
        return response

    user_id = g.current_user["user_id"]

    session_id = create_parking_session(
        user_id=user_id,
        spot_id=spot_id,
        hourly_rate=5.00,
        status="ON_HOLD"
    )
    fee_id = create_fee(
        user_id=user_id,
        session_id=session_id,
        description=f"Parking reservation for spot {spot_id}",
        cost=5.00,
        status="UNPAID",
    )

    return jsonify({
        "message": "Spot booked successfully.",
        "session_id": session_id,
        "spot_id": spot_id,
        "fee_id": fee_id,
        "payments_url": url_for("payments.payments_page"),
    })
