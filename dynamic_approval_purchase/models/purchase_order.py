from odoo import models, fields, _
from markupsafe import Markup
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    state = fields.Selection(
        selection_add=[
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ]
    )

    approval_request_id = fields.Many2one("approval.request", string="Approval Request")
    is_approved = fields.Boolean(default=False)
    is_approval_required = fields.Boolean(
        compute="_compute_is_approval_required", store=False
    )
    is_show_approve_reject_button = fields.Boolean(
        compute="_compute_show_approve_reject_button"
    )
    assigned_approver_id = fields.Many2one(
        related="approval_request_id.assigned_approver_id"
    )
    approver_state = fields.Selection(related="approval_request_id.approver_state")

    def _compute_show_approve_reject_button(self):
        current_user = self.env.user
        for rec in self:
            rec.is_show_approve_reject_button = False
            for line in rec.approval_request_id.approval_line_ids.sorted(
                key=lambda line: line.sequence
            ):
                if line.primary_approval_state in ["approved", "rejected"] or (
                    line.primary_approval_state == "skipped"
                    and line.secondary_approval_state in ["approved", "rejected"]
                ):
                    continue

                if rec.approval_request_id.state == "to_approve" and (
                    (
                        line.primary_approver == current_user
                        and line.primary_approval_state == "pending"
                    )
                    or (
                        line.secondary_approver == current_user
                        and line.primary_approval_state == "skipped"
                        and line.secondary_approval_state == "pending"
                    )
                ):
                    rec.is_show_approve_reject_button = True
                break

    def _compute_is_approval_required(self):
        for order in self:
            # Check if current user is the creator
            current_user = self.env.user
            is_creator = order.create_uid == current_user
            base_approval_required = self.env[
                "dynamic.approval.rule"
            ].is_approval_required(self.env, "purchase.order", order.id)
            order.is_approval_required = is_creator and base_approval_required

    def action_create_approval_request(self):
        self = self.sudo()
        for order in self:
            existing_approval_request = self.env["approval.request"].search(
                [
                    ("res_model", "=", "purchase.order"),
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

                order.is_approved = False
                order.state = "pending_approval"
                order.send_notification()
            else:
                approval_request = self.env[
                    "dynamic.approval.rule"
                ].create_approval_request(order)
                order.approval_request_id = approval_request.id or False
                order.state = "pending_approval"
                order.send_notification()

    # Approval Code start
    def send_notification(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref("dynamic_approval_rule.action_approval_request")
        action_url = (
            f"{base_url}/web#id={self.approval_request_id.id}"
            f"&action={action.id}"
            f"&model=approval.request"
            f"&view_type=form"
        )

        for rec in self:
            if rec.approval_request_id:
                first_line = rec.approval_request_id.approval_line_ids.sorted(
                    key=lambda x: x.sequence
                )[:1]
                if first_line and first_line.primary_approver:
                    message = f"""
                            New RFQ <b>{rec.name}</b> requires your approval.<br/>
                            <a href="{action_url}" target="_blank">Click here to view requisition lines</a>
                        """

                    # Send notification and email using message_notify
                    self.env["mail.thread"].message_notify(
                        partner_ids=first_line.primary_approver.partner_id.ids,
                        body=Markup(message),
                        subject="RFQ Approval Request",
                        res_id=rec.id,
                        record_name=rec.name,
                        email_layout_xmlid="mail.mail_notification_light",
                    )

                    self.env["mail.mail"].create(
                        {
                            "subject": "RFQ Approval Request",
                            "body_html": message,
                            "email_to": first_line.primary_approver.email,
                            "auto_delete": False,
                        }
                    ).send()

    def action_send_for_draft(self):
        self.state = "draft"
        self.is_approved = False

    def button_confirm(self):
        is_approved = self.is_approved
        # if not is_approved:
        #     raise UserError(_("This order requires approval before confirmation."))
        return super().button_confirm()

    def action_rfq_send(self):
        for order in self:
            if not order.is_approved:
                raise UserError(
                    _("This order requires approval before sending the quotation.")
                )
        return super().action_rfq_send()

    def print_quotation(self):
        is_approved = self.is_approved
        if not is_approved:
            raise UserError(_("This order requires approval before previewing."))
        return super().print_quotation()

    def action_approve(self):
        if self.approval_request_id:
            self.approval_request_id.action_approve()

    def action_reject(self):
        if self.approval_request_id:
            return self.approval_request_id.action_reject()
