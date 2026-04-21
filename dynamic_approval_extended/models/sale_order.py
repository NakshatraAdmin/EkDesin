from odoo import models
from markupsafe import Markup


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _compute_show_approve_reject_button(self):
        res = super()._compute_show_approve_reject_button()
        current_user = self.env.user
        for order in self:
            approval_request = order.approval_request_id
            if approval_request.approval_rule_id.approval_type == "parallel":
                order.is_show_approve_reject_button = (
                    approval_request._has_parallel_pending_action(current_user)
                )
        return res

    def send_notification(self):
        parallel_orders = self.filtered(
            lambda order: order.approval_request_id.approval_rule_id.approval_type
            == "parallel"
        )
        sequential_orders = self - parallel_orders
        if sequential_orders:
            super(SaleOrder, sequential_orders).send_notification()

        if not parallel_orders:
            return None

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref("dynamic_approval_sale.sale_order_approval_form_action")

        for order in parallel_orders:
            approval_request = order.approval_request_id
            approvers = approval_request._get_parallel_pending_approver_users()
            if not approvers:
                continue

            action_url = f"{base_url}/odoo/action-{action.id}/{order.id}"
            message = f"""
                    New approval for Quotation <b>{order.name}</b> requires your approval.<br/>
                    <a href="{action_url}" target="_blank">Click here to view request</a>
                """

            partner_ids = approvers.mapped("partner_id").ids
            if partner_ids:
                self.env["mail.thread"].message_notify(
                    partner_ids=partner_ids,
                    body=Markup(message),
                    subject="Quotation Approval Request",
                    res_id=order.id,
                    record_name=order.name,
                    email_layout_xmlid="mail.mail_notification_light",
                )

            for approver in approvers.filtered("email"):
                self.env["mail.mail"].create(
                    {
                        "subject": "Quotation Approval Request",
                        "body_html": message,
                        "email_to": approver.email,
                        "auto_delete": False,
                    }
                ).send()

        return None
