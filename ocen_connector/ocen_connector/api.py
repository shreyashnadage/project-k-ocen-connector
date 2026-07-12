"""Whitelisted API methods for OCEN Connector."""

from __future__ import annotations

import frappe
from frappe import _

from ocen_connector.utils import get_platform_client, map_platform_status


@frappe.whitelist()
def on_invoice_submit(doc, method=None):
    """Hook called when a Sales Invoice is submitted. Auto-captures if enabled."""
    settings = frappe.get_single("OCEN Settings")
    if settings.auto_capture_invoices:
        capture_invoice(doc.name)


@frappe.whitelist()
def capture_invoice(invoice_name: str) -> dict:
    """Send a submitted Sales Invoice to the OCEN platform /invoices/captured endpoint."""
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    if invoice.docstatus != 1:
        frappe.throw(_("Only submitted invoices can be captured."))

    settings = frappe.get_single("OCEN Settings")
    session = get_platform_client()

    payload = {
        "participant_id": settings.participant_id,
        "invoice_number": invoice.name,
        "irn": invoice.irn or "",
        "vendor_gstin": invoice.company_gstin or "",
        "anchor_gstin": invoice.billing_address_gstin or "",
        "invoice_date": str(invoice.posting_date),
        "due_date": str(invoice.due_date) if invoice.due_date else None,
        "total_amount": float(invoice.grand_total),
        "currency": invoice.currency,
    }

    url = f"{settings.api_base_url}/invoices/captured"
    response = session.post(url, json=payload)
    response.raise_for_status()

    frappe.msgprint(_("Invoice captured on OCEN platform."), alert=True)
    return response.json()


@frappe.whitelist()
def apply_for_loan(invoice_name: str, amount: float) -> dict:
    """Create an OCEN Loan Application and call the platform /loans/apply endpoint."""
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    settings = frappe.get_single("OCEN Settings")
    session = get_platform_client()

    payload = {
        "participant_id": settings.participant_id,
        "invoice_number": invoice.name,
        "irn": invoice.irn or "",
        "vendor_gstin": invoice.company_gstin or "",
        "anchor_gstin": invoice.billing_address_gstin or "",
        "invoice_date": str(invoice.posting_date),
        "amount_requested": float(amount),
    }

    url = f"{settings.api_base_url}/loans/apply"
    response = session.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    loan_app = frappe.get_doc(
        {
            "doctype": "OCEN Loan Application",
            "application_id": data.get("application_id", ""),
            "invoice": invoice.name,
            "invoice_id": data.get("invoice_id", ""),
            "vendor_gstin": invoice.company_gstin or "",
            "anchor_gstin": invoice.billing_address_gstin or "",
            "amount_requested": float(amount),
            "status": "Initiated",
            "workflow_id": data.get("workflow_id", ""),
            "platform_response": frappe.as_json(data),
        }
    )
    loan_app.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"loan_application": loan_app.name, "platform_response": data}


@frappe.whitelist()
def check_status(application_name: str) -> dict:
    """Poll the platform for loan application status and update local record."""
    loan_app = frappe.get_doc("OCEN Loan Application", application_name)
    settings = frappe.get_single("OCEN Settings")
    session = get_platform_client()

    url = f"{settings.api_base_url}/loans/status"
    response = session.post(url, json={"application_id": loan_app.application_id})
    response.raise_for_status()
    data = response.json()

    new_status = map_platform_status(data.get("status", ""))
    if new_status:
        loan_app.status = new_status
    loan_app.current_gate = data.get("current_gate", "")
    loan_app.workflow_id = data.get("workflow_id", loan_app.workflow_id)
    loan_app.offer_amount = data.get("offer_amount") or 0
    loan_app.offer_rate = data.get("offer_rate") or 0
    loan_app.offer_tenure_days = data.get("offer_tenure_days") or 0
    loan_app.lender_name = data.get("lender_name", "")
    loan_app.platform_response = frappe.as_json(data)
    loan_app.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": loan_app.status, "data": data}
