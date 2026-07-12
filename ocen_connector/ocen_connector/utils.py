"""Utility functions for OCEN Connector."""

from __future__ import annotations

import requests

import frappe


def get_platform_client() -> requests.Session:
    """Return a configured requests Session with API key header."""
    settings = frappe.get_single("OCEN Settings")
    session = requests.Session()
    session.headers.update(
        {
            "Content-Type": "application/json",
            "X-API-Key": settings.get_password("api_key") or "",
            "X-Participant-ID": settings.participant_id or "",
        }
    )
    session.timeout = 30
    return session


STATUS_MAP = {
    "initiated": "Initiated",
    "d0_passed": "D0 Passed",
    "aa_data_received": "AA Data Received",
    "d1_passed": "D1 Passed",
    "d2_passed": "D2 Passed",
    "d3_passed": "D3 Passed",
    "submitted_to_lender": "Submitted to Lender",
    "offer_received": "Offer Received",
    "offer_accepted": "Offer Accepted",
    "disbursed": "Disbursed",
    "rejected": "Rejected",
    "expired": "Expired",
}


def map_platform_status(status_str: str) -> str:
    """Map platform status string to DocType select option."""
    return STATUS_MAP.get(status_str.lower().strip(), "")
