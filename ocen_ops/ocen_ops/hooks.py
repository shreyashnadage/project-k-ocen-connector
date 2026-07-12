app_name = "ocen_ops"
app_title = "OCEN Ops"
app_publisher = "Project K"
app_description = "OCEN Operations Back-Office — CRM + Loan Management for OCEN LA Platform"
app_email = "shreyashnadage@gmail.com"
app_license = "MIT"
required_apps = ["frappe", "lending"]

# Document Events
doc_events = {
    "Customer": {
        "after_insert": "ocen_ops.ocen_ops.crm.sync.on_customer_created",
        "on_update": "ocen_ops.ocen_ops.crm.sync.on_customer_updated",
    },
    "OCEN Ops Action": {
        "after_insert": "ocen_ops.ocen_ops.ops.actions.dispatch_to_platform",
    },
}

# Scheduled Tasks
scheduler_events = {
    "cron": {
        "*/15 * * * *": [
            "ocen_ops.ocen_ops.ops.reconcile.run_reconciliation",
        ],
    },
}

# Fixtures (exported on bench export-fixtures)
fixtures = [
    {
        "dt": "Role",
        "filters": [["name", "in", [
            "OCEN Ops Manager",
            "OCEN Ops Viewer",
            "OCEN Collections",
            "OCEN CRM Manager",
        ]]],
    },
    {
        "dt": "Custom Field",
        "filters": [["fieldname", "like", "ocen_%"]],
    },
]

# Jinja template extensions
jenv = {
    "methods": [],
}
