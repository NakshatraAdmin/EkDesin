from odoo import models, _
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    def action_approve(self):
        res = super().action_approve()
        if self.res_model == "purchase.order":
            purchase_order = self.env["purchase.order"].browse(self.res_id)
            if not purchase_order:
                raise UserError(_("Purchase Order not found."))
            purchase_order.message_post(
                body=_("Approval request approved"),
                subject=_("Approval Approved"),
            )
            if self.state == "approved":
                purchase_order.is_approved = True
                purchase_order.state = "approved"
        return res

    def update_approver_and_state(self):
        res = super().update_approver_and_state()
        if self.res_model == "purchase.order" and self.state in [
            "approved",
            "rejected",
        ]:
            purchase_order = self.env["purchase.order"].browse(self.res_id)
            if not purchase_order:
                raise UserError(_("Purchase Order not found."))

            if self.state == "approved":
                purchase_order.is_approved = True
                purchase_order.state = "approved"
            elif self.state == "rejected":
                purchase_order.is_approved = False
                purchase_order.state = "rejected"
                purchase_order.message_post(
                    body=f"Approval Rejected: {self.rejection_reason}",
                    subject=_("Approval Rejected"),
                )
        return res
