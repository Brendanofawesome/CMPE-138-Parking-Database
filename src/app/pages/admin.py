from flask import Blueprint, render_template, request

admin_bp = Blueprint("admin", __name__)

# mock data (Phase 1)
sessions = [
    {"plate": "ABC123", "spot": "A1", "status": "active", "start_time": "10:00", "expired": False},
    {"plate": "XYZ789", "spot": "B2", "status": "expired", "start_time": "08:00", "expired": True},
]

fees = []


@admin_bp.route("/admin/plate-check", methods=["GET", "POST"])
def plate_check_page():
    result = None
    message = None
    message_type = None
    ticket = None

    if request.method == "POST":
        plate_input = request.form.get("plate", "").strip().upper()
        action = request.form.get("action", "check")

        for s in sessions:
            if s["plate"] == plate_input:
                result = s
                break

        if result is None:
            message = "No session found for this plate."
            message_type = "error"

        elif action == "issue_ticket":
            existing = [f for f in fees if f["plate"] == plate_input]

            if existing:
                message = "Ticket already issued."
                message_type = "warning"
            elif result["expired"]:
                ticket = {
                    "plate": plate_input,
                    "type": "violation",
                    "amount": 50,
                    "status": "unpaid"
                }
                fees.append(ticket)
                message = "Ticket issued!"
                message_type = "success"
            else:
                message = "Session is not expired."
                message_type = "warning"

        else:
            message = f"Found session for {plate_input}"
            message_type = "success"

    return render_template(
        "admin_plate_check.html",
        result=result,
        message=message,
        message_type=message_type,
        ticket=ticket,
    )
