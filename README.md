# OCEN Ops — Frappe Back-Office for OCEN LA Platform

Enterprise Frappe app providing CRM + Loan Management for the OCEN Loan Agent platform. Acts as the operational back-office where your ops team manages vendors, tracks loan lifecycle, and intervenes when needed.

## What It Does

- **CRM**: Manage anchors (buyers) and vendors (borrowers) as Customers in ERPNext
- **Loan Tracking**: Mirror platform loan state in real-time via webhooks
- **Ops Actions**: Hold/release applications, flag for review, escalate to collections
- **Lending Integration**: Auto-create Loan → Disbursement → Repayment records in frappe/lending
- **Bidirectional Onboarding**: Ops invites vendors from Frappe OR vendors self-register on PWA

## Architecture

```
Platform (Temporal + FastAPI)
    │
    ├── Webhooks (HMAC-signed) ──→ ocen_ops webhook receiver
    │                                   │
    │                                   ▼
    │                            OCEN Loan Application (status mirror)
    │                            Vendor/Anchor Onboarding
    │                            frappe/lending Loan docs
    │
    └── Ops Command API ←──── OCEN Ops Action (after_insert hook)
```

## Installation

```bash
# Prerequisites: Frappe Bench with ERPNext + frappe/lending installed

# Install the app
bench get-app https://github.com/shreyashnadage/project-k-ocen-connector

# Install on your site
bench --site your-site.local install-app ocen_ops

# Run migrations
bench --site your-site.local migrate
```

## Configuration

Add to `sites/your-site.local/site_config.json`:

```json
{
  "ocen_platform_url": "http://platform-instance:8000",
  "ocen_ops_api_key": "your-ops-api-key",
  "ocen_webhook_secret": "your-webhook-secret"
}
```

## Doctypes

| Doctype | Purpose |
|---------|---------|
| OCEN Loan Application | Mirrors platform loan state. Shows gate progress, offers, ops flags. |
| OCEN Ops Action | Audit log of every ops intervention (hold, release, flag, escalate). |
| Vendor Onboarding | Tracks vendor registration, PWA invite status, KYC. |
| Anchor Onboarding | Tracks anchor setup, repayment routing status. |
| Platform Webhook Log | Inbound webhook audit trail. |

## Roles

| Role | Access |
|------|--------|
| OCEN Ops Manager | Full CRUD on loan applications + ops actions |
| OCEN Ops Viewer | Read-only on all OCEN docs |
| OCEN Collections | Can escalate + create collection actions |
| OCEN CRM Manager | CRUD on Customers + onboarding docs |

## API Endpoints

### Webhook Receiver (Platform → Frappe)
```
POST /api/method/ocen_ops.ocen_ops.api.receive_platform_webhook
Headers: X-Platform-Signature (HMAC-SHA256)
```

### Application Status
```
GET /api/method/ocen_ops.ocen_ops.api.get_application_status?platform_application_id=...
```

## Dependencies

- Frappe Framework v15+
- ERPNext (for Customer doctype)
- frappe/lending (for Loan, Loan Disbursement, Loan Repayment)

## License

MIT
