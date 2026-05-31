{
    "name": "THA Partial Payment",
    "summary": "Group partial payment wizard for customer invoices and vendor bills",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Thein Htoo Aung",
    "license": "LGPL-3",
    "depends": [
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/partial_payment_wizard_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
