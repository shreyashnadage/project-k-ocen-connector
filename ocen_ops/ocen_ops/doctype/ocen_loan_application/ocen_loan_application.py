import frappe
from frappe.model.document import Document


class OCENLoanApplication(Document):
    def validate(self):
        if self.ops_hold and not self.ops_hold_reason:
            frappe.throw("Hold reason is required when placing an ops hold.")
