from __future__ import annotations

app_name = "ocen_connector"
app_title = "OCEN Connector"
app_publisher = "Shreyash Nadage"
app_description = "Connects vendor ERPNext instances to the OCEN LA platform for receivables financing"
app_email = "shreyashnadage@gmail.com"
app_license = "MIT"

doc_events = {
    "Sales Invoice": {
        "on_submit": "ocen_connector.api.on_invoice_submit",
    },
}

scheduler_events = {
    "cron": {
        "*/5 * * * *": [
            "ocen_connector.tasks.poll_loan_statuses",
        ],
    },
}
