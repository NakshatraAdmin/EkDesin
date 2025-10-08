from odoo import models, fields
from markupsafe import Markup


class StockPicking(models.Model):
    _inherit = "stock.picking"

    approval_request_id = fields.Many2one("approval.request")
    is_approval_required = fields.Boolean(
        compute="_compute_is_approval_required", store=False
    )
    state = fields.Selection(
        selection_add=[
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Stage",
        tracking=True,
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

    def action_approve(self):
        if self.approval_request_id:
            self.approval_request_id.action_approve()

    def action_reject(self):
        if self.approval_request_id:
            return self.approval_request_id.action_reject()

    def _compute_is_approval_required(self):
        for picking in self:
            picking.is_approval_required = self.env[
                "dynamic.approval.rule"
            ].is_approval_required(self.env, "stock.picking", picking.id)

    # Approval Code start
    def send_notification(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        if self.picking_type_id.code == "incoming":
            action = self.env.ref("stock.action_picking_tree_incoming")
        else:
            action = self.env.ref("stock.action_picking_tree_outgoing")
        action_url = f"{base_url}/odoo/action-{action.id}/{self.id}"

        for rec in self:
            if rec.approval_request_id:
                first_line = rec.approval_request_id.approval_line_ids.sorted(
                    key=lambda x: x.sequence
                )[:1]
                if first_line and first_line.primary_approver:
                    message = f"""
                            New Stock Created and it requires your approval.<br/>
                            <a href="{action_url}" target="_blank">Click here to view Stock</a>
                        """

                    # Send notification and email using message_notify
                    self.env["mail.thread"].message_notify(
                        partner_ids=first_line.primary_approver.partner_id.ids,
                        body=Markup(message),
                        subject="BoM Approval Request",
                        res_id=rec.id,
                        record_name=rec.product_id.display_name,
                        email_layout_xmlid="mail.mail_notification_light",
                    )

                    self.env["mail.mail"].create(
                        {
                            "subject": "BoM Approval Request",
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
                    ("res_model", "=", "stock.picking"),
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
        self.action_create_approval_request()
        self.send_notification()

    def button_send_to_draft(self):
        if self.state == "rejected":
            self.state = "draft"
