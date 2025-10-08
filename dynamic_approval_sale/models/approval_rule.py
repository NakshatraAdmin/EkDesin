from odoo import models
from markupsafe import Markup


class DynamicApprovalRule(models.Model):
    _inherit = "dynamic.approval.rule"

    def _send_notification(self, user, approval_request):
        if not user or not user.partner_id:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")

        if approval_request.res_model == "sale.order":
            action = self.env.ref("dynamic_approval_rule.action_approval_request")
            action_url = (
                f"{base_url}/web#id={approval_request.id}"
                f"&action={action.id}"
                f"&model=approval.request"
                f"&view_type=form"
            )
            req = (
                self.env[approval_request.res_model]
                .sudo()
                .browse(approval_request.res_id)
            )

            body = Markup(
                f"Reminder: Please approve Quotation <b>{req.name}</b>.<br/>"
                f"<a href='{action_url}' target='_blank'>Click to view</a>"
            )

            if approval_request.approval_rule_id.notify_in_app:
                user.partner_id.message_notify(
                    body=body,
                    subject="Approval Reminder",
                    partner_ids=[user.partner_id.id],
                )

            if approval_request.approval_rule_id.notify_email and user.email:
                mail_vals = {
                    "subject": f"Reminder: Approval Needed for Quotation - {req.name}",
                    "body_html": f"<p>{body}</p>",
                    "email_to": user.email,
                    "auto_delete": True,
                    "author_id": user.partner_id.id,
                }
                approval_request.env["mail.mail"].create(mail_vals).send()
        else:
            return super()._send_notification(user, approval_request)

    def _do_post_action(self, request, line, role):
        res = super()._do_post_action(request, line, role)

        if request.res_model == "sale.order":
            if role == "primary":
                action = line.primary_post_reminder_action
            else:
                action = line.secondary_post_reminder_action

            if action == "reallocate":
                sale_order = self.env["sale.order"].sudo().browse(request.res_id)
                if not sale_order:
                    return res
                msg = f"Approval skipped by <b>{line.primary_approver.name}</b>. Reallocated to secondary approver <b>{line.secondary_approver.name}</b>."
                sale_order.message_post(body=Markup(msg), message_type="notification")
        return res
