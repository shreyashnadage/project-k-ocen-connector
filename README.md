# OCEN Connector

Frappe/ERPNext custom app that connects vendor ERP instances to the OCEN LA platform for receivables financing via REST APIs.

## Installation

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/shreyashnadage/project-k-ocen-connector.git
bench --site your-site install-app ocen_connector
```

## Configuration

1. Navigate to **OCEN Settings** in your ERPNext instance.
2. Set the **API Base URL** (e.g., `https://ocen-platform.example.com`).
3. Enter your **API Key** and **Participant ID** (provided by the OCEN LA platform).
4. Enable/disable **Auto Capture Invoices** (captures invoices on submit).

## Usage

### Automatic Invoice Capture

When enabled, every submitted Sales Invoice is automatically sent to the OCEN platform's `/invoices/captured` endpoint.

### Apply for a Loan

From the browser console or a custom button:

```python
frappe.call({
    method: "ocen_connector.api.apply_for_loan",
    args: { invoice_name: "SINV-00001", amount: 500000 },
    callback: function(r) { console.log(r.message); }
});
```

### Status Polling

A scheduler job runs every 5 minutes to poll the platform for status updates on all active loan applications. You can also manually check:

```python
frappe.call({
    method: "ocen_connector.api.check_status",
    args: { application_name: "OCEN-LOAN-00001" }
});
```

## DocTypes

- **OCEN Settings** — singleton for platform configuration
- **OCEN Loan Application** — tracks each loan application lifecycle through D0-D3 gates

## License

MIT
