"""Scheduled tasks for OCEN Connector."""

from __future__ import annotations

import frappe

from ocen_connector.utils import get_platform_client, map_platform_status

TERMINAL_STATUSES = {"Disbursed", "Rejected", "Expired"}


def poll_loan_statuses():
    """Poll platform for status updates on all non-terminal loan applications."""
    applications = frappe.get_all(
        "OCEN Loan Application",
        filters={"status": ["not in", list(TERMINAL_STATUSES)]},
        fields=["name", "application_id"],
    )

    if not applications:
        return

    settings = frappe.get_single("OCEN Settings")
    session = get_platform_client()
    url = f"{settings.api_base_url}/loans/status"

    for app in applications:
        if not app.application_id:
            continue
        try:
            response = session.post(url, json={"application_id": app.application_id})
            response.raise_for_status()
            data = response.json()

            loan_app = frappe.get_doc("OCEN Loan Application", app.name)
            new_status = map_platform_status(data.get("status", ""))
            if new_status and new_status != loan_app.status:
                loan_app.status = new_status
                loan_app.current_gate = data.get("current_gate", "")
                loan_app.offer_amount = data.get("offer_amount") or 0
                loan_app.offer_rate = data.get("offer_rate") or 0
                loan_app.offer_tenure_days = data.get("offer_tenure_days") or 0
                loan_app.lender_name = data.get("lender_name", "")
                loan_app.platform_response = frappe.as_json(data)
                loan_app.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                title=f"OCEN Status Poll Failed: {app.name}",
                message=frappe.get_traceback(),
            )

    frappe.db.commit()
