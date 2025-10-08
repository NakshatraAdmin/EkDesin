from odoo import models
from markupsafe import Markup


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Approval Code start
    def send_notification(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref("stock.stock_product_normal_action")
        action_url = f"{base_url}/odoo/action-{action.id}/{self.id}"

        for rec in self:
            if rec.approval_request_id:
                first_line = rec.approval_request_id.approval_line_ids.sorted(
                    key=lambda x: x.sequence
                )[:1]
                if first_line and first_line.primary_approver:
                    message = f"""
                            New Product Created and it requires your approval.<br/>
                            <a href="{action_url}" target="_blank">Click here to view products</a>
                        """

                    # Send notification and email using message_notify
                    self.env["mail.thread"].message_notify(
                        partner_ids=first_line.primary_approver.partner_id.ids,
                        body=Markup(message),
                        subject="Product Approval Request",
                        res_id=rec.id,
                        record_name=rec.display_name,
                        email_layout_xmlid="mail.mail_notification_light",
                    )

                    self.env["mail.mail"].create(
                        {
                            "subject": "Product Approval Request",
                            "body_html": message,
                            "email_to": first_line.primary_approver.email,
                            "auto_delete": False,
                        }
                    ).send()

    def action_create_approval_request(self):
        self = self.sudo()
        for order in self:
            # approval_request = self.env[
            #     "dynamic.approval.rule"
            # ].create_approval_request(order)
            # self.approval_request_id = (
            #     approval_request.id if approval_request else False
            # )
            # self.approval_request_id.state = "to_approve"

            existing_approval_request = self.env["approval.request"].search(
                [
                    ("res_model", "=", "product.product"),
                    ("res_id", "=", order.id),
                    ("state", "in", ["rejected"]),
                ]
            )
            if existing_approval_request:
                existing_approval_request.state = "to_approve"
                for line in existing_approval_request.approval_line_ids:
                    line.primary_approval_state = "pending"
                    line.secondary_approval_state = "pending"

                approval_request = self.env[
                    "dynamic.approval.rule"
                ].create_approval_request(order)
            else:
                approval_request = self.env[
                    "dynamic.approval.rule"
                ].create_approval_request(order)

                order.approval_request_id = approval_request.id or False

    # Approval Code End

    def button_send_for_approval(self):
        self = self.sudo()
        self.state = "pending_approval"
        # # create approval request
        self.action_create_approval_request()
        self.send_notification()

    def button_send_to_draft(self):
        if self.state == "rejected":
            self.state = False
