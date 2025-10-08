from odoo import models, _
from markupsafe import Markup
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    def action_approve(self):
        res = super(ApprovalRequest, self).action_approve()
        if self.res_model == "mrp.bom":
            bom_id = self.env["mrp.bom"].sudo().browse(int(self.res_id))
            bom_id.message_post(
                body=_("Approval request approved"),
                subject=_("Approval Approved"),
            )
            if self.state == "approved":
                bom_id.sudo().state = "approved"
        return res

    def update_approver_and_state(self):
        res = super().update_approver_and_state()
        if self.res_model == "mrp.bom" and self.state in ["approved", "rejected"]:
            bom_id = self.env["mrp.bom"].browse(self.res_id)
            if not bom_id:
                raise UserError(_("Bill of Material not found."))

            if self.state == "approved":
                bom_id.state = "approved"
            elif self.state == "rejected":
                bom_id.state = "rejected"
                bom_id.message_post(
                    body=f"Approval Rejected: {self.rejection_reason}",
                    subject=_("Approval Rejected"),
                )
        return res

    def send_notification(self, req, action_by, state):
        """Send in-app notification and plain email when PR approval step is taken"""
        if self.res_model == "mrp.bom":
            approval_request = req
            if not approval_request:
                return

            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            action = self.env.ref("mrp.mrp_bom_form_action")
            action_url = f"{base_url}/odoo/action-{action.id}/{self.res_id}"

            # Message body for both email and in-app
            message = f"""
                    New Bill of Materials Created and it requires your approval.<br/>
                    <a href="{action_url}" target="_blank">Click here to view Bill of Materials</a>
                """

            # Recipients
            recipients = []

            # Notify request owner
            if (
                approval_request.request_owner_id
                and approval_request.request_owner_id.partner_id
            ):
                recipients.append(approval_request.request_owner_id)

            # Notify next approver (multi-level only)
            if approval_request.approval_rule_id.approval_level == "multi":
                for line in approval_request.approval_line_ids.sorted(
                    key=lambda x: x.sequence
                ):
                    if (
                        line.primary_approval_state == "pending"
                        and line.secondary_approval_state == "pending"
                    ):
                        if line.primary_approver and line.primary_approver != action_by:
                            recipients.append(line.primary_approver)
                        break

            for user in set(recipients):
                # check notification require or not
                if approval_request.approval_rule_id.notify_in_app and user.partner_id:
                    self.env["mail.thread"].sudo().message_notify(
                        body=Markup(message),
                        subject="Approval Update",
                        partner_ids=[user.partner_id.id],
                        res_id=approval_request.id,
                        record_name=approval_request.name,
                        email_layout_xmlid="mail.mail_notification_light",
                    )

                # Send plain email
                if (
                    approval_request.approval_rule_id.notify_email
                    and user.email
                    and user.partner_id
                ):
                    mail_values = {
                        "subject": f"Approval Update - {approval_request.name}",
                        "body_html": f"<p>{message}</p>",
                        "email_to": user.email,
                        "auto_delete": True,
                        "author_id": self.env.user.partner_id.id,
                    }
                    self.env["mail.mail"].sudo().create(mail_values).send()
        else:
            return super(ApprovalRequest, self).send_notification(req, action_by, state)
