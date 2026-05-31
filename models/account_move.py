from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    _tha_partial_payment_move_types = {
        "out_invoice",
        "in_invoice",
        "out_refund",
        "in_refund",
    }

    def _tha_validate_partial_payment_moves(self):
        moves = self.exists()
        if not moves:
            raise UserError(_("Please select at least one document."))

        invalid_types = moves.filtered(lambda move: move.move_type not in self._tha_partial_payment_move_types)
        if invalid_types:
            raise UserError(_("Only customer invoices, vendor bills, customer credit notes, and vendor refunds can be partially paid."))

        draft_moves = moves.filtered(lambda move: move.state == "draft")
        if draft_moves:
            raise UserError(_("Draft documents cannot be paid. Please post them first."))

        cancelled_moves = moves.filtered(lambda move: move.state == "cancel")
        if cancelled_moves:
            raise UserError(_("Cancelled documents cannot be paid."))

        not_posted_moves = moves.filtered(lambda move: move.state != "posted")
        if not_posted_moves:
            raise UserError(_("You can only create partial payments for posted documents."))

        fully_paid_moves = moves.filtered(lambda move: move.currency_id.is_zero(abs(move.amount_residual)))
        if fully_paid_moves:
            raise UserError(_("Fully paid documents cannot be selected."))

        if len(moves.company_id) != 1:
            raise UserError(_("All selected documents must belong to the same company."))

        return moves

    def action_open_group_partial_payment_wizard(self):
        moves = self._tha_validate_partial_payment_moves()
        return {
            "name": _("Group Partial Payment"),
            "type": "ir.actions.act_window",
            "res_model": "tha.partial.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "account.move",
                "active_ids": moves.ids,
            },
        }
