"""CRM sync — handles Customer creation events.

When ops creates a Customer tagged as vendor/anchor, this module
syncs the record to the platform and creates onboarding docs.
"""

import json

import frappe
import requests


def on_customer_created(doc, method=None):
    """After a Customer is created, check if it should be synced to platform."""
    # Only process if the customer has OCEN-relevant custom fields
    if not doc.tax_id or len(doc.tax_id) != 15:
        return

    # Determine if this is a vendor or anchor based on customer_group
    # Convention: "Anchor" group = anchor, everything else = vendor
    is_anchor = doc.customer_group and "anchor" in doc.customer_group.lower()

    if is_anchor:
        _sync_anchor_to_platform(doc)
    else:
        _sync_vendor_to_platform(doc)


def on_customer_updated(doc, method=None):
    """Handle Customer updates — propagate relevant changes."""
    pass


def _sync_vendor_to_platform(doc):
    """Create a vendor invite on the platform when ops creates a vendor Customer."""
    platform_url = frappe.conf.get("ocen_platform_url", "http://localhost:8000")
    api_key = frappe.conf.get("ocen_ops_api_key", "")

    if not api_key:
        return

    # Check if Vendor Onboarding already exists
    if frappe.db.exists("Vendor Onboarding", {"gstin": doc.tax_id}):
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": doc.customer_name,
        "gstin": doc.tax_id,
        "phone": doc.mobile_no or "0000000000",
        "invited_by": frappe.session.user,
    }

    try:
        response = requests.post(
            f"{platform_url}/ops/vendor/invite",
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            # Create Vendor Onboarding doc
            frappe.get_doc({
                "doctype": "Vendor Onboarding",
                "customer": doc.name,
                "gstin": doc.tax_id,
                "platform_vendor_id": data.get("vendor_id", ""),
                "pwa_invite_sent": 1,
                "pwa_invite_token": data.get("invite_token", ""),
                "sync_status": "Synced",
            }).insert(ignore_permissions=True)
            frappe.db.commit()

    except requests.RequestException as e:
        frappe.log_error(f"Vendor sync to platform failed: {e}")


def _sync_anchor_to_platform(doc):
    """Create an anchor on the platform when ops creates an anchor Customer."""
    platform_url = frappe.conf.get("ocen_platform_url", "http://localhost:8000")
    api_key = frappe.conf.get("ocen_ops_api_key", "")

    if not api_key:
        return

    if frappe.db.exists("Anchor Onboarding", {"gstin": doc.tax_id}):
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": doc.customer_name,
        "gstin": doc.tax_id,
        "sector": "",
        "region": doc.territory or "",
        "onboarded_by": frappe.session.user,
    }

    try:
        response = requests.post(
            f"{platform_url}/ops/anchor/onboard",
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            frappe.get_doc({
                "doctype": "Anchor Onboarding",
                "customer": doc.name,
                "gstin": doc.tax_id,
                "platform_anchor_id": data.get("anchor_id", ""),
                "sync_status": "Synced",
            }).insert(ignore_permissions=True)
            frappe.db.commit()

    except requests.RequestException as e:
        frappe.log_error(f"Anchor sync to platform failed: {e}")
