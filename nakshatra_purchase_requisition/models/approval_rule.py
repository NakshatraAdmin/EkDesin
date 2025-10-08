from odoo import models
from markupsafe import Markup


class DynamicApprovalRule(models.Model):
    _inherit = "dynamic.approval.rule"    

    def _do_post_action(self, request, line, role):
        res = super()._do_post_action(request, line, role)

        if request.res_model == "nakshatra.purchase.requisition":
            if role == "primary":
                action = line.primary_post_reminder_action
            else:
                action = line.secondary_post_reminder_action

            if action == "reallocate":
                sale_order = self.env["nakshatra.purchase.requisition"].sudo().browse(request.res_id)
                if not sale_order:
                    return res
                msg = f"Approval skipped by <b>{line.primary_approver.name}</b>. Reallocated to secondary approver <b>{line.secondary_approver.name}</b>."
                sale_order.message_post(body=Markup(msg), message_type="notification")
        return res
