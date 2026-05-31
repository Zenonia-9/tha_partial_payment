from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError


class ThaPartialPaymentWizardLine(models.TransientModel):
    _name = "tha.partial.payment.wizard.line"
    _description = "Partial Payment Wizard Line"
    _order = "invoice_date_due, move_id"

    wizard_id = fields.Many2one(
        "tha.partial.payment.wizard",
        required=True,
        ondelete="cascade",
    )
    move_id = fields.Many2one(
        "account.move",
        string="Document",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        readonly=True,
    )
    move_type = fields.Selection(
        related="move_id.move_type",
        string="Move Type",
        readonly=True,
    )
    partner_type = fields.Selection(
        selection=[
            ("customer", "Customer"),
            ("supplier", "Vendor"),
        ],
        readonly=True,
    )
    invoice_date = fields.Date(readonly=True)
    invoice_date_due = fields.Date(readonly=True)
    currency_id = fields.Many2one(
        "res.currency",
        readonly=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        readonly=True,
    )
    amount_total = fields.Monetary(
        readonly=True,
        currency_field="currency_id",
    )
    amount_residual = fields.Monetary(
        string="Due Amount",
        readonly=True,
        currency_field="currency_id",
    )
    applied_amount = fields.Monetary(
        string="Applied",
        currency_field="currency_id",
    )
    payment_direction = fields.Selection(
        selection=[
            ("inbound", "Receive Money"),
            ("outbound", "Send Money"),
        ],
        readonly=True,
    )


class ThaPartialPaymentWizard(models.TransientModel):
    _name = "tha.partial.payment.wizard"
    _description = "Group Partial Payment"
    _check_company_auto = True

    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        required=True,
        check_company=True,
        domain="[('id', 'in', available_journal_ids)]",
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment Method",
        required=True,
        domain="[('id', 'in', available_payment_method_line_ids)]",
    )
    payment_date = fields.Date(
        string="Payment Date",
        required=True,
        default=fields.Date.context_today,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
    )
    communication = fields.Char(string="Memo")
    group_payment = fields.Boolean(
        string="Group Payments",
        default=True,
        help="Enabled: create one payment for all compatible documents. Disabled: create one payment per document.",
    )
    payment_type = fields.Selection(
        selection=[
            ("outbound", "Send Money"),
            ("inbound", "Receive Money"),
        ],
        string="Payment Type",
        readonly=True,
    )
    partner_type = fields.Selection(
        selection=[
            ("customer", "Customer"),
            ("supplier", "Vendor"),
        ],
        readonly=True,
    )
    line_ids = fields.One2many(
        "tha.partial.payment.wizard.line",
        "wizard_id",
        string="Documents",
    )
    amount_total_applied = fields.Monetary(
        string="Total Applied",
        compute="_compute_amount_total_applied",
        currency_field="currency_id",
    )
    available_journal_ids = fields.Many2many(
        "account.journal",
        compute="_compute_available_journal_ids",
    )
    available_payment_method_line_ids = fields.Many2many(
        "account.payment.method.line",
        compute="_compute_available_payment_method_line_ids",
    )
    available_partner_bank_ids = fields.Many2many(
        "res.partner.bank",
        compute="_compute_available_partner_bank_ids",
    )
    partner_bank_id = fields.Many2one(
        "res.partner.bank",
        string="Recipient Bank Account",
        domain="[('id', 'in', available_partner_bank_ids)]",
        check_company=True,
    )
    show_partner_bank_account = fields.Boolean(
        compute="_compute_show_require_partner_bank",
    )
    require_partner_bank_account = fields.Boolean(
        compute="_compute_show_require_partner_bank",
    )

    PAYMENT_PROFILE_BY_MOVE_TYPE = {
        "out_invoice": ("inbound", "customer"),
        "in_invoice": ("outbound", "supplier"),
        "out_refund": ("outbound", "customer"),
        "in_refund": ("inbound", "supplier"),
    }

    @api.depends("line_ids.applied_amount")
    def _compute_amount_total_applied(self):
        for wizard in self:
            wizard.amount_total_applied = sum(wizard.line_ids.mapped("applied_amount"))

    @api.depends("company_id", "line_ids.payment_direction")
    def _compute_available_journal_ids(self):
        Journal = self.env["account.journal"]
        for wizard in self:
            if not wizard.company_id:
                wizard.available_journal_ids = Journal
                continue
            directions = set(wizard.line_ids.mapped("payment_direction")) or {wizard.payment_type or "inbound"}
            journals = Journal.search([
                ("company_id", "=", wizard.company_id.id),
                ("type", "in", ("bank", "cash", "credit")),
            ])
            for direction in directions:
                journals = journals.filtered(lambda journal: journal._get_available_payment_method_lines(direction))
            wizard.available_journal_ids = journals

    @api.depends("journal_id", "payment_type", "line_ids.payment_direction")
    def _compute_available_payment_method_line_ids(self):
        MethodLine = self.env["account.payment.method.line"]
        for wizard in self:
            if not wizard.journal_id:
                wizard.available_payment_method_line_ids = MethodLine
                continue
            direction = wizard.payment_type or (wizard.line_ids[:1].payment_direction if wizard.line_ids else "inbound")
            wizard.available_payment_method_line_ids = wizard.journal_id._get_available_payment_method_lines(direction)

    @api.depends("journal_id", "payment_type", "partner_id", "company_id")
    def _compute_available_partner_bank_ids(self):
        PartnerBank = self.env["res.partner.bank"]
        for wizard in self:
            if not wizard.journal_id:
                wizard.available_partner_bank_ids = PartnerBank
            elif wizard.payment_type == "inbound":
                wizard.available_partner_bank_ids = wizard.journal_id.bank_account_id
            elif wizard.partner_id:
                wizard.available_partner_bank_ids = wizard.partner_id.bank_ids.filtered(
                    lambda bank: bank.company_id.id in (False, wizard.company_id.id)
                )._origin
            else:
                wizard.available_partner_bank_ids = PartnerBank

    @api.depends("payment_method_line_id", "journal_id")
    def _compute_show_require_partner_bank(self):
        payment_model = self.env["account.payment"]
        method_codes_using_bank = payment_model._get_method_codes_using_bank_account()
        method_codes_needing_bank = payment_model._get_method_codes_needing_bank_account()
        for wizard in self:
            if wizard.journal_id.type == "cash":
                wizard.show_partner_bank_account = False
            else:
                wizard.show_partner_bank_account = wizard.payment_method_line_id.code in method_codes_using_bank
            wizard.require_partner_bank_account = wizard.payment_method_line_id.code in method_codes_needing_bank

    @api.onchange("journal_id", "payment_type", "partner_id")
    def _onchange_journal_id(self):
        for wizard in self:
            if wizard.payment_method_line_id not in wizard.available_payment_method_line_ids:
                wizard.payment_method_line_id = wizard.available_payment_method_line_ids[:1]
            if wizard.partner_bank_id not in wizard.available_partner_bank_ids:
                wizard.partner_bank_id = wizard.available_partner_bank_ids[:1]

    @api.model
    def _get_payment_profile(self, move):
        return self.PAYMENT_PROFILE_BY_MOVE_TYPE.get(move.move_type)

    @api.model
    def _get_counterpart_lines(self, move):
        profile = self._get_payment_profile(move)
        if not profile:
            return self.env["account.move.line"]
        partner_type = profile[1]
        account_type = "asset_receivable" if partner_type == "customer" else "liability_payable"
        return move.line_ids.filtered(
            lambda line: (
                line.account_id.account_type == account_type
                and not line.reconciled
                and line.parent_state == "posted"
            )
        )

    @api.model
    def _prepare_line_command(self, move):
        payment_direction, _partner_type = self._get_payment_profile(move)
        return Command.create({
            "move_id": move.id,
            "partner_id": move.partner_id.id,
            "partner_type": _partner_type,
            "invoice_date": move.invoice_date,
            "invoice_date_due": move.invoice_date_due,
            "currency_id": move.currency_id.id,
            "company_currency_id": move.company_currency_id.id,
            "amount_total": abs(move.amount_total),
            "amount_residual": abs(move.amount_residual),
            "applied_amount": abs(move.amount_residual),
            "payment_direction": payment_direction,
        })

    @api.model
    def _get_common_record(self, records):
        records = records.filtered(lambda record: record)
        return records[:1] if len(records) == 1 else False

    @api.model
    def _get_default_journal(self, company, directions):
        journals = self.env["account.journal"].search([
            ("company_id", "=", company.id),
            ("type", "in", ("bank", "cash", "credit")),
        ])
        for direction in directions:
            journals = journals.filtered(lambda journal: journal._get_available_payment_method_lines(direction))
        return journals[:1]

    @api.model
    def _get_default_partner_bank(self, journal, payment_type, partner, company):
        if not journal:
            return self.env["res.partner.bank"]
        if payment_type == "inbound":
            return journal.bank_account_id
        if partner:
            return partner.bank_ids.filtered(lambda bank: bank.company_id.id in (False, company.id))[:1]._origin
        return self.env["res.partner.bank"]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids") or []
        active_id = self.env.context.get("active_id")
        if not active_ids and active_id:
            active_ids = [active_id]

        if self.env.context.get("active_model") and self.env.context.get("active_model") != "account.move":
            raise UserError(_("Group Partial Payment must be opened from invoices or bills."))

        moves = self.env["account.move"].browse(active_ids).exists()
        moves = moves._tha_validate_partial_payment_moves()

        missing_counterpart = moves.filtered(lambda move: not self._get_counterpart_lines(move))
        if missing_counterpart:
            raise UserError(_("Every selected document must have an open receivable or payable line."))

        directions = {self._get_payment_profile(move)[0] for move in moves}
        partner_types = {self._get_payment_profile(move)[1] for move in moves}
        company = moves.company_id
        first_move = moves[:1]
        journal = self._get_default_journal(company, directions)
        if not journal:
            raise UserError(_("No bank, cash, or credit journal with valid payment methods was found for the selected documents."))

        payment_type = next(iter(directions)) if len(directions) == 1 else first_move and self._get_payment_profile(first_move)[0]
        partner_type = next(iter(partner_types)) if len(partner_types) == 1 else first_move and self._get_payment_profile(first_move)[1]
        payment_method = journal._get_available_payment_method_lines(payment_type)[:1]
        common_partner = self._get_common_record(moves.partner_id)
        common_currency = self._get_common_record(moves.currency_id) or company.currency_id

        labels = [move.payment_reference or move.ref or move.name for move in moves]
        res.update({
            "company_id": company.id,
            "partner_id": common_partner.id if common_partner else False,
            "currency_id": common_currency.id,
            "payment_type": payment_type,
            "partner_type": partner_type,
            "journal_id": journal.id,
            "payment_method_line_id": payment_method.id,
            "partner_bank_id": self._get_default_partner_bank(journal, payment_type, common_partner, company).id,
            "payment_date": fields.Date.context_today(self),
            "communication": ", ".join(label for label in labels if label),
            "group_payment": True,
            "line_ids": [self._prepare_line_command(move) for move in moves],
        })
        return res

    def _positive_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(lambda line: line.currency_id.compare_amounts(line.applied_amount, 0.0) > 0)

    def _validate_amounts(self):
        self.ensure_one()
        for line in self.line_ids:
            if line.currency_id.compare_amounts(line.applied_amount, 0.0) < 0:
                raise UserError(_("Applied amount cannot be negative for %s.") % line.move_id.display_name)
            if line.currency_id.compare_amounts(line.applied_amount, line.amount_residual) > 0:
                raise UserError(_("Applied amount cannot be greater than the due amount for %s.") % line.move_id.display_name)

        if not self._positive_lines():
            raise UserError(_("At least one document must have an applied amount greater than zero."))

    def _validate_journal_and_method(self):
        self.ensure_one()
        if self.journal_id.company_id != self.company_id:
            raise UserError(_("The selected journal must belong to the selected company."))

        if self.payment_method_line_id.journal_id and self.payment_method_line_id.journal_id != self.journal_id:
            raise UserError(_("The selected payment method is not valid for the selected journal."))

        if self.require_partner_bank_account and not self.partner_bank_id:
            raise UserError(_("Recipient Bank Account is required for the selected payment method."))

        if self.partner_bank_id and self.partner_bank_id not in self.available_partner_bank_ids:
            raise UserError(_("The selected Recipient Bank Account is not valid for this payment."))

        for direction in set(self._positive_lines().mapped("payment_direction")):
            if not self.journal_id._get_available_payment_method_lines(direction):
                raise UserError(_("The selected journal has no valid %s payment method.") % dict(self.line_ids._fields["payment_direction"].selection)[direction])

    def _validate_group_payment(self):
        self.ensure_one()
        lines = self._positive_lines()
        checks = (
            ("move_id.company_id", _("Grouped payments cannot mix companies.")),
            ("partner_id", _("Grouped payments cannot mix different customers or vendors.")),
            ("currency_id", _("Grouped payments cannot mix different currencies.")),
            ("payment_direction", _("Grouped payments cannot mix inbound and outbound documents.")),
            ("partner_type", _("Grouped payments cannot mix customer and vendor documents.")),
        )
        for field_name, message in checks:
            values = lines.mapped(field_name)
            unique_count = len(set(values)) if isinstance(values, list) else len(values)
            if unique_count != 1:
                raise UserError(message)

        move_types = set(lines.mapped("move_type"))
        invalid_pairs = (
            {"out_invoice", "out_refund"},
            {"in_invoice", "in_refund"},
        )
        if any(pair.issubset(move_types) for pair in invalid_pairs):
            raise UserError(_("Grouped payments cannot mix invoices/bills with their credit notes or refunds."))

    def _get_payment_method_for_direction(self, direction):
        self.ensure_one()
        method_lines = self.journal_id._get_available_payment_method_lines(direction)
        if self.payment_method_line_id in method_lines:
            return self.payment_method_line_id
        method_line = method_lines[:1]
        if not method_line:
            raise UserError(_("No valid payment method is available for %s payments on the selected journal.") % direction)
        return method_line

    def _get_destination_account(self, move):
        counterpart_lines = self._get_counterpart_lines(move)
        account = counterpart_lines[:1].account_id
        if not account:
            raise UserError(_("No open receivable or payable account line was found for %s.") % move.display_name)
        return account

    def _get_liquidity_account(self, payment):
        account = (
            payment.outstanding_account_id
            or payment.payment_method_line_id.payment_account_id
            or payment.journal_id.default_account_id
        )
        if not account:
            raise UserError(_("No liquidity account could be found on the selected journal or payment method."))
        return account

    def _get_partner_bank(self, move):
        self.ensure_one()
        if self.partner_bank_id:
            return self.partner_bank_id
        payment_direction, _partner_type = self._get_payment_profile(move)
        if payment_direction == "inbound":
            return self.journal_id.bank_account_id
        return move.partner_id.bank_ids.filtered(
            lambda bank: bank.company_id.id in (False, move.company_id.id)
        )[:1]._origin

    def _payment_vals(self, amount, line, payment_method_line):
        self.ensure_one()
        move = line.move_id
        payment_direction, partner_type = self._get_payment_profile(move)
        vals = {
            "date": self.payment_date,
            "amount": amount,
            "payment_type": payment_direction,
            "partner_type": partner_type,
            "memo": self.communication or move.payment_reference or move.ref or move.name,
            "journal_id": self.journal_id.id,
            "company_id": move.company_id.id,
            "currency_id": move.currency_id.id,
            "partner_id": move.partner_id.id,
            "payment_method_line_id": payment_method_line.id,
            "destination_account_id": self._get_destination_account(move).id,
            "write_off_line_vals": [],
        }
        partner_bank = self._get_partner_bank(move)
        if partner_bank:
            vals["partner_bank_id"] = partner_bank.id
        return vals

    def _get_counterpart_split_vals(self, payment, lines, balance_total):
        self.ensure_one()
        amount_currency_sign = -1 if payment.payment_type == "inbound" else 1
        split_vals = []
        running_balance = 0.0

        for index, line in enumerate(lines):
            amount_currency = amount_currency_sign * line.applied_amount
            account = self._get_destination_account(line.move_id)
            if index == len(lines) - 1:
                balance = balance_total - running_balance
            else:
                balance = line.currency_id._convert(
                    amount_currency,
                    line.move_id.company_currency_id,
                    line.move_id.company_id,
                    self.payment_date,
                )
                running_balance += balance

            split_vals.append({
                "name": line.move_id.payment_reference or line.move_id.ref or line.move_id.name or payment.memo,
                "date_maturity": self.payment_date,
                "amount_currency": amount_currency,
                "currency_id": line.currency_id.id,
                "debit": balance if balance > 0.0 else 0.0,
                "credit": -balance if balance < 0.0 else 0.0,
                "partner_id": line.partner_id.id,
                "account_id": account.id,
            })
        return split_vals

    def _create_payment_move(self, payment, lines):
        liquidity_amount_currency = payment.amount if payment.payment_type == "inbound" else -payment.amount
        liquidity_balance = payment.currency_id._convert(
            liquidity_amount_currency,
            payment.company_id.currency_id,
            payment.company_id,
            payment.date,
        )
        liquidity_account = self._get_liquidity_account(payment)
        counterpart_balance = -liquidity_balance
        split_vals = self._get_counterpart_split_vals(payment, lines, counterpart_balance)

        liquidity_line_vals = {
            "name": payment.memo or payment.payment_method_line_id.name,
            "date_maturity": payment.date,
            "amount_currency": liquidity_amount_currency,
            "currency_id": payment.currency_id.id,
            "debit": liquidity_balance if liquidity_balance > 0.0 else 0.0,
            "credit": -liquidity_balance if liquidity_balance < 0.0 else 0.0,
            "partner_id": payment.partner_id.id,
            "account_id": liquidity_account.id,
        }

        move = self.env["account.move"].with_context(skip_invoice_sync=True).create({
            "move_type": "entry",
            "ref": payment.memo,
            "date": payment.date,
            "journal_id": payment.journal_id.id,
            "company_id": payment.company_id.id,
            "partner_id": payment.partner_id.id,
            "currency_id": payment.currency_id.id,
            "partner_bank_id": payment.partner_bank_id.id,
            "line_ids": [
                Command.create(liquidity_line_vals),
                *[Command.create(vals) for vals in split_vals],
            ],
            "origin_payment_id": payment.id,
        })
        payment.with_context(skip_invoice_sync=True).write({"move_id": move.id})
        new_counterpart_lines = payment._seek_for_lines()[1].sorted("id")
        return dict(zip(lines.ids, new_counterpart_lines.ids))

    def _split_group_payment_counterpart_lines(self, payment, lines):
        self.ensure_one()
        if not payment.move_id:
            return self._create_payment_move(payment, lines)

        liquidity_lines, counterpart_lines, writeoff_lines = payment._seek_for_lines()
        if len(counterpart_lines) != 1 or writeoff_lines:
            raise UserError(_("The payment journal entry could not be prepared for document-level partial reconciliation."))

        old_counterpart = counterpart_lines[0]
        split_vals = self._get_counterpart_split_vals(payment, lines, old_counterpart.balance)

        payment.move_id.with_context(skip_invoice_sync=True).write({
            "line_ids": [
                Command.delete(old_counterpart.id),
                *[Command.create(vals) for vals in split_vals],
            ],
        })
        new_counterpart_lines = payment._seek_for_lines()[1].sorted("id")
        return dict(zip(lines.ids, new_counterpart_lines.ids))

    def _reconcile_payment_line(self, payment, wizard_line, payment_line):
        invoice_lines = self._get_counterpart_lines(wizard_line.move_id).filtered(
            lambda line: line.account_id == payment_line.account_id and not line.reconciled
        )
        if not invoice_lines:
            raise UserError(_("No open receivable or payable line is available to reconcile %s.") % wizard_line.move_id.display_name)

        (invoice_lines + payment_line).filtered(lambda line: not line.reconciled).reconcile()
        wizard_line.move_id.matched_payment_ids += payment

    def _create_group_payment(self, lines):
        self.ensure_one()
        amount = sum(lines.mapped("applied_amount"))
        method_line = self._get_payment_method_for_direction(lines[0].payment_direction)
        payment = self.env["account.payment"].with_company(self.company_id).with_context(skip_invoice_sync=True).create(
            self._payment_vals(amount, lines[0], method_line)
        )
        split_line_ids = self._split_group_payment_counterpart_lines(payment, lines)
        payment.with_context(skip_sale_auto_invoice_send=True).action_post()
        for line in lines:
            payment_line = self.env["account.move.line"].browse(split_line_ids[line.id])
            self._reconcile_payment_line(payment, line, payment_line)
        return payment

    def _create_separate_payments(self, lines):
        self.ensure_one()
        payments = self.env["account.payment"]
        for line in lines:
            method_line = self._get_payment_method_for_direction(line.payment_direction)
            payment = self.env["account.payment"].with_company(self.company_id).with_context(skip_invoice_sync=True).create(
                self._payment_vals(line.applied_amount, line, method_line)
            )
            split_line_ids = self._split_group_payment_counterpart_lines(payment, line)
            payment.with_context(skip_sale_auto_invoice_send=True).action_post()
            payment_line = self.env["account.move.line"].browse(split_line_ids[line.id])
            if not payment_line:
                raise UserError(_("No payment counterpart line was found for %s.") % line.move_id.display_name)
            self._reconcile_payment_line(payment, line, payment_line)
            payments |= payment
        return payments

    def action_create_payments(self):
        self.ensure_one()
        self.line_ids.move_id._tha_validate_partial_payment_moves()
        self._validate_amounts()
        self._validate_journal_and_method()
        positive_lines = self._positive_lines()

        if self.group_payment:
            self._validate_group_payment()
            payments = self._create_group_payment(positive_lines)
        else:
            payments = self._create_separate_payments(positive_lines)

        action = {
            "name": _("Payments"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "context": {"create": False},
        }
        if len(payments) == 1:
            action.update({
                "view_mode": "form",
                "res_id": payments.id,
            })
        else:
            action.update({
                "view_mode": "list,form",
                "domain": [("id", "in", payments.ids)],
            })
        return action
