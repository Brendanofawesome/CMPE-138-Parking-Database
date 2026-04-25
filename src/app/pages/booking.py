from flask import Blueprint, request, jsonify, g

from app.payment import create_parking_session  # adjust if your file name is different

booking_bp = Blueprint("booking", __name__)

@booking_bp.route("/book-spot", methods=["POST"])
def book_spot():
    if g.current_user is None:
        return jsonify({"error": "You must be logged in to book a spot."}), 401

    data = request.get_json()
    spot_id = data.get("spot_id") if data else None

    if not spot_id:
        return jsonify({"error": "Missing spot_id."}), 400

    user_id = g.current_user["user_id"]

    session_id = create_parking_session(
        user_id=user_id,
        spot_id=spot_id,
        hourly_rate=5.00,
        status="ON_HOLD"
    )

    return jsonify({
        "message": "Spot booked successfully.",
        "session_id": session_id,
        "spot_id": spot_id
    })