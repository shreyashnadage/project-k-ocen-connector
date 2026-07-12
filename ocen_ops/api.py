"""Whitelisted API endpoints for the OCEN Ops app.

Exposed at /api/method/ocen_ops.api.*
"""

import hashlib
import hmac
import json

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def receive_platform_webhook():
    """Inbound webhook from the OCEN platform.

    Authenticated via HMAC-SHA256 signature in X-Platform-Signature header.
    Creates/updates OCEN Loan Application docs and related records.
    """
    signature = frappe.request.headers.get("X-Platform-Signature", "")
    body = frappe.request.get_data()

    webhook_secret = frappe.conf.get("ocen_webhook_secret", "")
    if webhook_secret:
        expected = hmac.HMAC(
            webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

    payload = json.loads(body)
    event_type = payload.get("event_type", "")
    event_payload = payload.get("payload", {})

    # Log the webhook
    frappe.get_doc({
        "doctype": "Platform Webhook Log",
        "event_type": event_type,
        "payload": json.dumps(event_payload, indent=2),
        "processed": 0,
    }).insert(ignore_permissions=True)

    # Route to handler
    handler = WEBHOOK_HANDLERS.get(event_type)
    if handler:
        try:
            handler(payload)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Webhook handler error for {event_type}: {e}")
            frappe.db.rollback()

    return {"status": "ok", "event_type": event_type}


# ─── Helper: resolve OCEN Loan Application name from platform ID ────────


def _get_ocen_app_name(payload):
    """Extract platform_application_id from event and find the Frappe doc name."""
    app_data = payload.get("payload", payload)
    platform_id = app_data.get("correlation_id") or app_data.get("entity_id")
    if not platform_id:
        return None
    return frappe.db.get_value(
        "OCEN Loan Application", {"platform_application_id": platform_id}
    )


# ─── Handlers ──────────────────────────────────────────────────────────


def _handle_application_created(payload):
    """Create a new OCEN Loan Application doc."""
    app_data = payload.get("payload", payload)
    platform_id = app_data.get("entity_id") or app_data.get("platform_application_id")

    if not platform_id:
        return

    if frappe.db.exists("OCEN Loan Application", {"platform_application_id": platform_id}):
        return

    doc = frappe.get_doc({
        "doctype": "OCEN Loan Application",
        "platform_application_id": platform_id,
        "vendor_gstin": app_data.get("vendor_gstin", ""),
        "anchor_gstin": app_data.get("anchor_gstin", ""),
        "amount_requested": app_data.get("amount_requested", 0),
        "platform_status": "created",
        "current_gate": "d0_kind1_gate",
        "workflow_id": app_data.get("workflow_id", ""),
    })
    doc.insert(ignore_permissions=True)


def _handle_decision_evaluated(payload):
    """Update gate progress on OCEN Loan Application."""
    app_data = payload.get("payload", payload)
    platform_id = app_data.get("correlation_id") or app_data.get("entity_id")
    gate = app_data.get("gate", "")
    outcome = app_data.get("outcome", "")

    if not platform_id:
        return

    name = frappe.db.get_value(
        "OCEN Loan Application", {"platform_application_id": platform_id}
    )
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.current_gate = gate
    if outcome == "fail":
        doc.platform_status = "rejected"
    doc.save(ignore_permissions=True)


def _handle_offer_received(payload):
    """Store offer data when lender responds."""
    app_data = payload.get("payload", payload)
    name = _get_ocen_app_name(payload)
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.platform_status = "offer_received"
    doc.offer_data = json.dumps(app_data.get("offer", {}))
    doc.save(ignore_permissions=True)


def _handle_offer_accepted(payload):
    """Offer accepted — create Loan Application + Loan in frappe/lending."""
    name = _get_ocen_app_name(payload)
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.platform_status = "offer_accepted"
    doc.save(ignore_permissions=True)

    from ocen_ops.lending.lifecycle import create_loan_from_offer
    create_loan_from_offer(name)


def _handle_disbursed(payload):
    """Loan disbursed — create Loan Disbursement entry."""
    name = _get_ocen_app_name(payload)
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.platform_status = "disbursed"
    doc.save(ignore_permissions=True)

    from ocen_ops.lending.lifecycle import create_disbursement
    create_disbursement(name)


def _handle_repayment_observed(payload):
    """Repayment received — create Loan Repayment entry."""
    app_data = payload.get("payload", payload)
    name = _get_ocen_app_name(payload)
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.platform_status = "repaying"
    doc.save(ignore_permissions=True)

    amount = app_data.get("amount", 0)
    payment_ref = app_data.get("payment_reference", "")

    from ocen_ops.lending.lifecycle import create_repayment
    create_repayment(name, amount, payment_ref)


def _handle_closed(payload):
    """Loan closed — mark Loan as closed."""
    name = _get_ocen_app_name(payload)
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.platform_status = "closed"
    doc.save(ignore_permissions=True)

    from ocen_ops.lending.lifecycle import close_loan
    close_loan(name)


def _handle_status_update(payload, status):
    """Generic status update handler for events without lending side-effects."""
    name = _get_ocen_app_name(payload)
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.platform_status = status
    doc.save(ignore_permissions=True)


def _handle_ops_hold(payload):
    """Platform applied a hold — mirror to Frappe doc."""
    app_data = payload.get("payload", payload)
    name = _get_ocen_app_name(payload)
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.ops_hold = 1
    doc.ops_hold_reason = app_data.get("reason", "")
    doc.save(ignore_permissions=True)


def _handle_ops_released(payload):
    """Platform released a hold — mirror to Frappe doc."""
    name = _get_ocen_app_name(payload)
    if not name:
        return

    doc = frappe.get_doc("OCEN Loan Application", name)
    doc.ops_hold = 0
    doc.ops_hold_reason = ""
    doc.save(ignore_permissions=True)


def _handle_vendor_onboarded(payload):
    """Create Customer + Vendor Onboarding when platform registers a vendor."""
    app_data = payload.get("payload", payload)
    gstin = app_data.get("gstin", "")
    name = app_data.get("name", "")
    vendor_id = app_data.get("vendor_id") or app_data.get("entity_id", "")

    if not gstin:
        return

    if frappe.db.exists("Vendor Onboarding", {"gstin": gstin}):
        return

    # Create Customer if not exists
    if not frappe.db.exists("Customer", {"tax_id": gstin}):
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name or f"Vendor {gstin}",
            "customer_type": "Company",
            "customer_group": "Commercial",
            "territory": "India",
            "tax_id": gstin,
        })
        customer.insert(ignore_permissions=True)

    # Create Vendor Onboarding
    doc = frappe.get_doc({
        "doctype": "Vendor Onboarding",
        "gstin": gstin,
        "platform_vendor_id": str(vendor_id),
        "pwa_registered": 1,
        "sync_status": "Synced",
    })
    doc.insert(ignore_permissions=True)


# ─── Handler Registry ──────────────────────────────────────────────────


WEBHOOK_HANDLERS = {
    # Loan lifecycle — with lending side-effects
    "loan.application_created": _handle_application_created,
    "loan.decision_evaluated": _handle_decision_evaluated,
    "loan.submitted_to_lender": lambda p: _handle_status_update(p, "submitted_to_lender"),
    "loan.offer_received": _handle_offer_received,
    "loan.offer_accepted": _handle_offer_accepted,
    "loan.disbursed": _handle_disbursed,
    "loan.repayment_observed": _handle_repayment_observed,
    "loan.closed": _handle_closed,
    "loan.rejected": lambda p: _handle_status_update(p, "rejected"),
    # Ops events
    "ops.hold_applied": _handle_ops_hold,
    "ops.hold_released": _handle_ops_released,
    "ops.flag_added": lambda p: _handle_status_update(p, None),
    "ops.escalated": lambda p: _handle_status_update(p, None),
    # Vendor/Anchor lifecycle
    "vendor.onboarded": _handle_vendor_onboarded,
    "vendor.activated": _handle_vendor_onboarded,
    "vendor.invited": _handle_vendor_onboarded,
}


@frappe.whitelist(allow_guest=False)
def get_application_status(platform_application_id):
    """Quick lookup for platform to verify Frappe state."""
    name = frappe.db.get_value(
        "OCEN Loan Application", {"platform_application_id": platform_application_id}
    )
    if not name:
        frappe.throw(_("Application not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc("OCEN Loan Application", name)
    return {
        "platform_application_id": doc.platform_application_id,
        "platform_status": doc.platform_status,
        "current_gate": doc.current_gate,
        "ops_hold": doc.ops_hold,
        "linked_loan": doc.linked_loan,
    }
