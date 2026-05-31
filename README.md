# Partial Payment

![Odoo 19](https://img.shields.io/badge/Odoo-19.0-875A7B?style=flat-square)
![License](https://img.shields.io/badge/License-LGPL--3-blue?style=flat-square)
![Category](https://img.shields.io/badge/Category-Accounting-4ECDC4?style=flat-square)

Create partial payments for selected customer invoices, vendor bills, credit notes, and refunds in Odoo 19.

This addon adds a list-view payment workflow for posted accounting documents with open residual amounts. It keeps the technical module namespace as `tha_partial_payment`, while the visible module name remains business-facing as **Partial Payment**.

## Highlights

- Adds a **Partially Pay** button to the invoice and bill list view.
- Supports posted customer invoices, vendor bills, customer credit notes, and vendor refunds.
- Opens a wizard with editable applied amounts per selected document.
- Creates either one grouped payment or separate payments per document.
- Splits grouped payment counterpart lines so each document reconciles against its own applied amount.
- Blocks draft, cancelled, fully paid, invalid type, and multi-company selections.

## What It Changes

- Extends the invoice list view with a `Partially Pay` action.
- Adds a transient group partial payment wizard.
- Validates selected documents before payment creation.
- Creates and posts `account.payment` records through Odoo accounting models.
- Reconciles the created payment lines against the selected receivable or payable lines.

## Group Payment Rules

Grouped payments require selected documents to share the same company, partner, currency, payment direction, and partner type. The wizard also prevents grouping invoices or bills together with their credit notes or refunds.

## Technical Notes

- `models/account_move.py`
  Adds the list-view action and selection validation on `account.move`.
- `wizard/partial_payment_wizard.py`
  Provides the payment wizard, amount validation, payment creation, grouped counterpart splitting, and reconciliation logic.
- `views/account_move_views.xml`
  Adds the `Partially Pay` button to the invoice list view.
- `views/partial_payment_wizard_views.xml`
  Defines the wizard form and editable document lines.
- `security/ir.model.access.csv`
  Grants invoice users access to the transient wizard records.

## Module Layout

```text
tha_partial_payment/
|-- models/
|-- security/
|-- views/
|-- wizard/
`-- __manifest__.py
```

## Dependencies

- `account`

## Installation

1. Place the module in your custom addons path.
2. Update the Apps list in Odoo.
3. Install **Partial Payment**.

## License

This module is licensed under `LGPL-3`.
