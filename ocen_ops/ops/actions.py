"""Dispatch ops actions to the OCEN platform backend."""

import json

import frappe
import requests


def dispatch_to_platform(doc, method=None):
    """Called after_insert on OCEN Ops Action.

    Sends the ops command to the platform's Ops Command API.
    """
    platform_url = frappe.conf.get("ocen_platform_url", "http://localhost:8000")
    api_key = frappe.conf.get("ocen_ops_api_key", "")

    if not api_key:
        frappe.log_error("OCEN Ops API key not configured in site_config.json")
        return

    # Get the linked application's platform ID
    application = frappe.get_doc("OCEN Loan Application", doc.application)
    platform_application_id = application.platform_application_id

    # Map action_type to platform endpoint
    endpoint_map = {
        "hold": "/ops/hold",
        "release": "/ops/release",
        "flag": "/ops/flag",
        "escalate": "/ops/escalate",
    }

    endpoint = endpoint_map.get(doc.action_type)
    if not endpoint:
        frappe.log_error(f"Unknown action type: {doc.action_type}")
        return

    # Build request payload
    payload = {
        "application_id": platform_application_id,
        "reason": doc.reason,
    }

    if doc.action_type == "hold":
        payload["held_by"] = doc.performed_by or frappe.session.user
    elif doc.action_type == "release":
        payload["released_by"] = doc.performed_by or frappe.session.user
    elif doc.action_type == "flag":
        payload["flag_type"] = "manual_review"
        payload["note"] = doc.reason
        payload["flagged_by"] = doc.performed_by or frappe.session.user
    elif doc.action_type == "escalate":
        payload["escalated_by"] = doc.performed_by or frappe.session.user

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{platform_url}{endpoint}",
            json=payload,
            headers=headers,
            timeout=30,
        )

        doc.db_set("platform_ack", 1 if response.status_code < 300 else 0)
        doc.db_set("platform_response", json.dumps(response.json()))

        if response.status_code >= 300:
            frappe.log_error(
                f"Platform rejected ops action: {response.status_code} {response.text}"
            )

        # Update the application's ops_hold state
        if doc.action_type == "hold" and response.status_code < 300:
            application.db_set("ops_hold", 1)
            application.db_set("ops_hold_reason", doc.reason)
        elif doc.action_type == "release" and response.status_code < 300:
            application.db_set("ops_hold", 0)
            application.db_set("ops_hold_reason", "")

    except requests.RequestException as e:
        doc.db_set("platform_ack", 0)
        doc.db_set("platform_response", json.dumps({"error": str(e)}))
        frappe.log_error(f"Platform dispatch failed: {e}")
