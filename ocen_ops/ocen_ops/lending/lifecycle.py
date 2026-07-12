"""Frappe Lending integration — maps OCEN loan lifecycle to frappe/lending doctypes.

Called by the webhook handler when loan status transitions to key states.
"""

import json

import frappe


def create_loan_from_offer(ocen_app_name):
    """When offer is accepted, create Loan Application + Loan in frappe/lending.

    Args:
        ocen_app_name: Name of the OCEN Loan Application doc
    """
    doc = frappe.get_doc("OCEN Loan Application", ocen_app_name)

    if doc.linked_loan_application:
        return  # Already created

    offer = json.loads(doc.offer_data) if doc.offer_data else {}

    # Create Loan Application in frappe/lending
    loan_app = frappe.get_doc({
        "doctype": "Loan Application",
        "applicant_type": "Customer",
        "applicant": _get_customer_for_gstin(doc.vendor_gstin),
        "loan_type": _get_or_create_loan_type(),
        "loan_amount": offer.get("approved_amount") or doc.amount_requested,
        "repayment_method": "Repay Fixed Amount per Period",
        "repayment_periods": 1,  # Single bullet for short-tenure receivable finance
        "rate_of_interest": (offer.get("interest_rate_bps", 0) / 100),
        "status": "Approved",
    })
    loan_app.insert(ignore_permissions=True)
    loan_app.submit()

    # Link back
    doc.db_set("linked_loan_application", loan_app.name)

    # Create Loan from the approved application
    loan = frappe.get_doc({
        "doctype": "Loan",
        "applicant_type": "Customer",
        "applicant": loan_app.applicant,
        "loan_application": loan_app.name,
        "loan_type": loan_app.loan_type,
        "loan_amount": loan_app.loan_amount,
        "rate_of_interest": loan_app.rate_of_interest,
        "repayment_method": loan_app.repayment_method,
        "repayment_periods": loan_app.repayment_periods,
        "posting_date": frappe.utils.today(),
        "status": "Sanctioned",
    })
    loan.insert(ignore_permissions=True)
    loan.submit()

    doc.db_set("linked_loan", loan.name)
    frappe.db.commit()


def create_disbursement(ocen_app_name):
    """When loan is disbursed, create Loan Disbursement entry."""
    doc = frappe.get_doc("OCEN Loan Application", ocen_app_name)

    if not doc.linked_loan:
        return

    loan = frappe.get_doc("Loan", doc.linked_loan)

    disbursement = frappe.get_doc({
        "doctype": "Loan Disbursement",
        "against_loan": loan.name,
        "disbursement_date": frappe.utils.today(),
        "disbursed_amount": doc.amount_sanctioned or loan.loan_amount,
    })
    disbursement.insert(ignore_permissions=True)
    disbursement.submit()
    frappe.db.commit()


def create_repayment(ocen_app_name, amount, payment_reference=""):
    """When repayment is observed, create Loan Repayment entry."""
    doc = frappe.get_doc("OCEN Loan Application", ocen_app_name)

    if not doc.linked_loan:
        return

    repayment = frappe.get_doc({
        "doctype": "Loan Repayment",
        "against_loan": doc.linked_loan,
        "posting_date": frappe.utils.today(),
        "amount_paid": amount,
        "payable_amount": amount,
    })
    repayment.insert(ignore_permissions=True)
    repayment.submit()
    frappe.db.commit()


def close_loan(ocen_app_name):
    """When loan is fully repaid, close the Loan."""
    doc = frappe.get_doc("OCEN Loan Application", ocen_app_name)

    if not doc.linked_loan:
        return

    loan = frappe.get_doc("Loan", doc.linked_loan)
    loan.db_set("status", "Closed")
    frappe.db.commit()


def _get_customer_for_gstin(gstin):
    """Find Customer linked to this GSTIN."""
    customer = frappe.db.get_value("Customer", {"tax_id": gstin})
    if not customer:
        # Auto-create a minimal customer
        doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": f"Vendor {gstin}",
            "customer_type": "Company",
            "customer_group": "Commercial",
            "territory": "India",
            "tax_id": gstin,
        })
        doc.insert(ignore_permissions=True)
        return doc.name
    return customer


def _get_or_create_loan_type():
    """Get or create the OCEN Vendor Receivable loan type."""
    loan_type_name = "OCEN Vendor Receivable"

    if frappe.db.exists("Loan Type", loan_type_name):
        return loan_type_name

    loan_type = frappe.get_doc({
        "doctype": "Loan Type",
        "loan_name": loan_type_name,
        "rate_of_interest": 14,
        "maximum_loan_amount": 5000000,
        "description": "Working capital loan against confirmed receivable via OCEN network",
    })
    loan_type.insert(ignore_permissions=True)
    return loan_type.name
