"""Scheduled reconciliation — catches missed webhooks.

Runs every 15 minutes via scheduler_events in hooks.py.
Calls the platform's /ops/applications/active endpoint and syncs state.
"""

import json

import frappe
import requests


def run_reconciliation():
    """Reconcile active applications with platform state."""
    platform_url = frappe.conf.get("ocen_platform_url", "http://localhost:8000")
    api_key = frappe.conf.get("ocen_ops_api_key", "")

    if not api_key:
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(
            f"{platform_url}/ops/applications/active",
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            frappe.log_error(f"Reconciliation failed: {response.status_code}")
            return

        data = response.json()
        applications = data.get("applications", [])

        for app in applications:
            platform_id = str(app.get("application_id", ""))
            if not platform_id:
                continue

            name = frappe.db.get_value(
                "OCEN Loan Application",
                {"platform_application_id": platform_id},
            )

            if not name:
                # Application exists on platform but not in Frappe — create it
                frappe.get_doc({
                    "doctype": "OCEN Loan Application",
                    "platform_application_id": platform_id,
                    "vendor_gstin": app.get("vendor_gstin", ""),
                    "anchor_gstin": app.get("anchor_gstin", ""),
                    "amount_requested": app.get("amount_requested", 0),
                    "platform_status": app.get("status", "created"),
                    "current_gate": app.get("current_gate", ""),
                    "workflow_id": app.get("workflow_id", ""),
                }).insert(ignore_permissions=True)
            else:
                # Update status if changed
                doc = frappe.get_doc("OCEN Loan Application", name)
                platform_status = app.get("status", "")
                if platform_status and doc.platform_status != platform_status:
                    doc.platform_status = platform_status
                    doc.current_gate = app.get("current_gate", doc.current_gate)
                    doc.save(ignore_permissions=True)

        frappe.db.commit()

    except requests.RequestException as e:
        frappe.log_error(f"Reconciliation request failed: {e}")
