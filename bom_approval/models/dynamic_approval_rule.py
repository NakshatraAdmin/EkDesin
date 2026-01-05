from odoo import models
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class DynamicApprovalRule(models.Model):
    _inherit = "dynamic.approval.rule"

    def _send_notification(self, user, approval_request):
        if not user or not user.partner_id:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")

        if approval_request.res_model == "mrp.bom":
            action = self.env.ref("mrp.mrp_bom_form_action")
            action_url = f"{base_url}/odoo/action-{action.id}/{approval_request.res_id}"
            bom = (
                self.env[approval_request.res_model]
                .sudo()
                .browse(approval_request.res_id)
            )

            body = Markup(
                f"Reminder: Please approve Bill of Materials <b>{bom.product_id.display_name}</b>.<br/>"
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
                    "subject": f"Reminder: Approval Needed for BoMs - {bom.product_id.display_name}",
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

        if request.res_model == "mrp.bom":
            if role == "primary":
                action = line.primary_post_reminder_action
            else:
                action = line.secondary_post_reminder_action

            if action == "reallocate":
                bom = self.env["mrp.bom"].sudo().browse(request.res_id)
                if not bom:
                    return res
                msg = f"Approval skipped by <b>{line.primary_approver.name}</b>. Reallocated to secondary approver <b>{line.secondary_approver.name}</b>."
                bom.message_post(body=Markup(msg), message_type="notification")
        return res
