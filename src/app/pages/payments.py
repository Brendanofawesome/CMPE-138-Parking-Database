"""Payments page and fee payment actions."""

from __future__ import annotations

from flask import Blueprint, abort, g, redirect, render_template, url_for
from flask.typing import ResponseReturnValue

from app.payments import get_payment_page_data, get_transactions_page_data, record_payment

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("/payments", methods=["GET"])
def payments_page() -> ResponseReturnValue:
    current_user = g.get("current_user")
    if current_user is None:
        return redirect(url_for("login.login"))

    user_id = int(current_user["user_id"])
    payment_data = get_payment_page_data(user_id)
    transaction_data = get_transactions_page_data(user_id)
    return render_template(
        "payments.html",
        outstanding_fees=payment_data["outstanding_fees"],
        total_due=payment_data["total_due"],
        transactions=transaction_data["transactions"],
        total_paid=transaction_data["total_paid"],
    )


@payments_bp.route("/payments/pay/<int:fee_id>", methods=["POST"])
def pay_fee(fee_id: int) -> ResponseReturnValue:
    current_user = g.get("current_user")
    if current_user is None:
        return redirect(url_for("login.login"))

    user_id = int(current_user["user_id"])
    payment_data = get_payment_page_data(user_id)
    fee_to_pay = next((fee for fee in payment_data["outstanding_fees"] if fee.fee_id == fee_id), None)
    if fee_to_pay is None:
        abort(404)

    record_payment(fee_id=fee_id, amount=fee_to_pay.cost, method="CARD")
    return redirect(url_for("payments.payments_page"))
