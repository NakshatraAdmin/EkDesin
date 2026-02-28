from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from collections import defaultdict
from markupsafe import Markup
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PRLineApprovalWizard(models.TransientModel):
    _name = "pr.line.approval.wizard"
    _description = "Approve or Reject PR Line Items"

    line_ids = fields.One2many("pr.line.approval.line", "wizard_id", string="Lines")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        selected_ids = self.env.context.get("active_ids", [])
        lines = self.env["nakshatra.purchase.requisition.line"].browse(selected_ids)
        res["line_ids"] = [
            (
                0,
                0,
                {
                    "pr_id": line.pr_id.id,
                    "prl_id": line.id,
                    "product_id": line.product_id.id,
                    "requested_qty": line.requested_qty,
                    "approved_qty": line.requested_qty,
                },
            )
            for line in lines
        ]
        return res

    def send_notification(self, pr_id, action_by, state):
        """Send in-app notification and plain email when PR approval step is taken"""

        approval_request = pr_id.approval_request_id
        if not approval_request:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref(
            "nakshatra_purchase_requisition.action_purchase_requisition_line"
        )
        action_url = f"{base_url}/web#action={action.id}&model=nakshatra.purchase.requisition.line&view_type=list"

        # Message body for both email and in-app
        message = (
            f"Purchase Requisition <b>{pr_id.name}</b> has been <b>{state.upper()}</b> by <b>{action_by.name}</b>.<br/>"
            f"<a href='{action_url}' target='_blank'>View Requisition Lines</a>"
        )

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
            if (
                pr_id.approval_request_id.approval_rule_id.notify_in_app
                and user.partner_id
            ):
                self.env["mail.thread"].message_notify(
                    body=Markup(message),
                    subject="Approval Update",
                    partner_ids=[user.partner_id.id],
                    res_id=pr_id.id,
                    record_name=pr_id.name,
                    email_layout_xmlid="mail.mail_notification_light",
                )

            # Send plain email
            if (
                pr_id.approval_request_id.approval_rule_id.notify_email
                and user.email
                and user.partner_id
            ):
                mail_values = {
                    "subject": f"Approval Update - {pr_id.name}",
                    "body_html": f"<p>{message}</p>",
                    "email_to": user.email,
                    "auto_delete": True,
                    "author_id": self.env.user.partner_id.id,
                }
                self.env["mail.mail"].create(mail_values).send()

    def check_for_approval(self):
        """Approve PR Lines and handle approval logic"""
        self = self.sudo()
        current_user = self.env.user
        # Get the PR from the first line
        if self.line_ids:
            pr_id = self.line_ids[0].prl_id.pr_id
            # Handle approval logic once
            if pr_id.approval_request_id.approval_rule_id.approval_level == "single":
                # Single level approval logic
                for approver_line in pr_id.approval_request_id.approval_line_ids:
                    if current_user.id == approver_line.primary_approver.id:
                        approver_line.write({"primary_approval_state": "approved"})
                        pr_id.approval_request_id.update_approver_and_state()
                        self.send_notification(pr_id, current_user, "approved")
                        break
                    elif current_user.id == approver_line.secondary_approver.id:
                        approver_line.write({"primary_approval_state": "approved"})
                        pr_id.approval_request_id.update_approver_and_state()
                        self.send_notification(pr_id, current_user, "approved")
                        break
                    else:
                        raise UserError(
                            _("You are not assigned in the current approval step.")
                        )
            else:
                # Multi-level approval logic
                if not pr_id.approval_request_id:
                    raise UserError(_("No approval request found."))

                approval_lines = pr_id.approval_request_id.approval_line_ids.sorted(
                    key=lambda x: x.sequence
                )

                for approval_line in approval_lines:
                    # Skip lines that are already completed
                    if approval_line.primary_approval_state in (
                        "approved",
                        "rejected",
                    ) or approval_line.secondary_approval_state in (
                        "approved",
                        "rejected",
                    ):
                        continue

                    # Current line is the first pending one
                    if (
                        approval_line.primary_approval_state == "pending"
                        and approval_line.secondary_approval_state == "pending"
                    ):
                        if current_user.id == approval_line.primary_approver.id:
                            approval_line.write({"primary_approval_state": "approved"})
                            pr_id.approval_request_id.update_approver_and_state()
                            self.send_notification(pr_id, current_user, "approved")
                            break
                        elif current_user.id == approval_line.secondary_approver.id:
                            if approval_line.primary_approval_state != "skipped":
                                raise UserError(
                                    _(
                                        "Waiting for primary approver to approve/skipped before you can approve."
                                    )
                                )

                            approval_line.write(
                                {"secondary_approval_state": "approved"}
                            )
                            self.send_notification(pr_id, current_user, "approved")
                            break
                        else:
                            raise UserError(
                                _("You are not assigned in the current approval step.")
                            )

                    # If the line has already been approved by one of the two
                    if (
                        approval_line.primary_approval_state == "approved"
                        and current_user.id == approval_line.secondary_approver.id
                    ) or (
                        approval_line.secondary_approval_state == "approved"
                        and current_user.id == approval_line.primary_approver.id
                    ):
                        raise UserError(
                            _(
                                "This step has already been approved by another approver."
                            )
                        )

                    # If current user is trying to act on a line not assigned to them
                    if current_user.id not in [
                        approval_line.primary_approver.id,
                        approval_line.secondary_approver.id,
                    ]:
                        raise UserError(
                            _(
                                "Previous approval step is pending. You cannot proceed further."
                            )
                        )

    def button_approve(self):
        self = self.sudo()
        post_msg_dict = {}
        self.check_for_approval()
        pr_id = self.line_ids[0].prl_id.pr_id

        # Check if approval lines are all approved (multi-level)
        all_approved = all(
            line.primary_approval_state == "approved"
            or line.secondary_approval_state == "approved"
            for line in pr_id.approval_request_id.approval_line_ids
        )

        for line in self.line_ids:
            pr_line = line.prl_id.sudo()
            # Update original line
            pr_line.write(
                {
                    "approved_qty": line.approved_qty,
                }
            )
            if line.approved_qty <= pr_line.requested_qty:
                rejected_qty = pr_line.requested_qty - line.approved_qty
                # Create rejected line
                if post_msg_dict.get(line.pr_id):
                    post_msg_dict[line.pr_id] += (
                        "Product: %s \n | Requested Qty: %s \n | Rejected Qty: %s \n | Approved Qty: %s \n | Reject Reason: %s <br/>"
                        % (
                            pr_line.product_id.name,
                            pr_line.requested_qty,
                            rejected_qty,
                            line.approved_qty,
                            line.reject_reason or "",
                        )
                    )
                else:
                    post_msg_dict[line.pr_id] = (
                        "Product: %s \n | Requested Qty: %s \n | Rejected Qty: %s \n | Approved Qty: %s \n | Reject Reason: %s <br/>"
                        % (
                            pr_line.product_id.name,
                            pr_line.requested_qty,
                            rejected_qty,
                            line.approved_qty,
                            line.reject_reason or "",
                        )
                    )
            if line.approved_qty == 0:
                pr_line.write(
                    {
                        "item_status": "rejected",
                    }
                )
            else:
                if post_msg_dict.get(line.pr_id):
                    post_msg_dict[line.pr_id] += "Approved: %s , Qty: %s\n" % (
                        pr_line.product_id.name,
                        line.approved_qty,
                    )
                else:
                    post_msg_dict[line.pr_id] = "Approved: %s , Qty: %s\n" % (
                        pr_line.product_id.name,
                        line.approved_qty,
                    )
            pr_id = pr_line.pr_id

            # Proceed only if all approval lines are done
            if all_approved:
                pr_line.write(
                    {
                        "item_status": "approved"
                        if line.approved_qty == pr_line.requested_qty
                        else "partially_approved",
                    }
                )
                has_to_approve = any(
                    line.item_status == "to_approve" for line in pr_id.line_ids
                )
                has_rejected = any(
                    line.item_status == "rejected" for line in pr_id.line_ids
                )
                has_approved = any(
                    line.item_status == "approved" for line in pr_id.line_ids
                )
                has_partially_approved = any(
                    line.item_status == "partially_approved" for line in pr_id.line_ids
                )

                if has_partially_approved or has_approved and has_to_approve:
                    pr_id.state = "partially_approved"
                elif has_approved and not has_rejected and not has_to_approve:
                    pr_id.state = "approved"
                elif has_approved and has_rejected:
                    pr_id.state = "partially_approved"
                elif has_rejected and has_to_approve:
                    pr_id.state = "to_approve"
                else:
                    pr_id.state = "cancelled"

                # Update the approval request state based on the PR state
                pr_id.approval_request_id.write(
                    {
                        "state": pr_id.state,
                    }
                )

                grouped_lines = defaultdict(list)

                for line in self.line_ids:
                    if line.approved_qty > 0:
                        pr_line = line.prl_id
                        product = pr_line.product_id
                        params = {
                            "quantity": pr_line.approved_qty,
                            "date": pr_line.date_planned,
                        }
                        seller = product._prepare_sellers(params=params)
                        if not seller:
                            continue  # skip if no vendor found

                        vendor_id = seller[0].partner_id.id
                        project_id = pr_line.pr_id.project_id.id

                        if grouped_lines.get(
                            (vendor_id, project_id)
                        ) and pr_line.product_id.id in [
                            line.product_id.id
                            for line in grouped_lines.get((vendor_id, project_id))
                        ]:
                            for line in grouped_lines.get((vendor_id, project_id)):
                                if line.product_id.id == pr_line.product_id.id:
                                    line += pr_line
                        grouped_lines[(vendor_id, project_id)] += pr_line

                for (vendor_id, project_id), lines in grouped_lines.items():
                    rfq = self.env["purchase.order"].create(
                        {
                            "partner_id": vendor_id,
                            "project_id": project_id,
                            "order_line": [
                                (
                                    0,
                                    0,
                                    {
                                        "product_id": line.product_id.id,
                                        "pr_id": line.pr_id.id,
                                        "name": line.product_id.display_name,
                                        "product_qty": line.approved_qty,
                                        "product_uom": line.product_id.uom_id.id,
                                        "date_planned": line.date_planned
                                        or fields.Date.today(),
                                    },
                                )
                                for line in lines
                            ],
                        }
                    )
                    # Optionally link PR lines to the RFQ
                    for line in lines:
                        line.write({"po_id": rfq.id})

        # Post message to PR
        for post_msg in post_msg_dict:
            post_msg.message_post(body=Markup(post_msg_dict[post_msg]))

        grouped_lines = defaultdict(list)

        for line in self.line_ids:
            if line.approved_qty > 0:
                pr_line = line.prl_id
                product = pr_line.product_id
                params = {
                    "quantity": pr_line.approved_qty,
                    "date": pr_line.date_planned,
                }
                seller = product._prepare_sellers(params=params)
                if not seller:
                    continue  # skip if no vendor found

                vendor_id = seller[0].partner_id.id
                project_id = pr_line.pr_id.project_id.id

                if grouped_lines.get(
                    (vendor_id, project_id)
                ) and pr_line.product_id.id in [
                    line.product_id.id
                    for line in grouped_lines.get((vendor_id, project_id))
                ]:
                    for line in grouped_lines.get((vendor_id, project_id)):
                        if line.product_id.id == pr_line.product_id.id:
                            line += pr_line
                grouped_lines[(vendor_id, project_id)] += pr_line

        for (vendor_id, project_id), lines in grouped_lines.items():
            rfq = self.env["purchase.order"].create(
                {
                    "partner_id": vendor_id,
                    "project_id": project_id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": line.product_id.id,
                                "pr_id": line.pr_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.approved_qty,
                                "product_uom": line.product_id.uom_id.id,
                                "date_planned": line.date_planned
                                or fields.Date.today(),
                            },
                        )
                        for line in lines
                    ],
                }
            )
            # Optionally link PR lines to the RFQ
            for line in lines:
                line.write({"po_id": rfq.id})


class PRLineApprovalLine(models.TransientModel):
    _name = "pr.line.approval.line"
    _description = "PR Line for Approval Wizard"

    wizard_id = fields.Many2one("pr.line.approval.wizard", ondelete="cascade")
    requisition_line_id = fields.Integer(string="PR item")
    pr_number = fields.Char(string="PR No")
    pr_id = fields.Many2one(
        "nakshatra.purchase.requisition", string="Purchase Requisition"
    )
    prl_id = fields.Many2one(
        "nakshatra.purchase.requisition.line", string="Purchase Requisition item"
    )
    project_id = fields.Many2one(related="pr_id.project_id")
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    requested_qty = fields.Float(readonly=True)
    approved_qty = fields.Float()
    rejected_qty = fields.Float()
    reject_reason = fields.Text(string="Rejection Reason")

    @api.onchange("approved_qty")
    def _onchange_approved_qty(self):
        if self.requested_qty and self.approved_qty is not None:
            if self.approved_qty > self.requested_qty:
                self.approved_qty = 0
                raise ValidationError(_("Approved qty cannot exceed requested qty."))
            self.rejected_qty = self.requested_qty - self.approved_qty

    @api.onchange("rejected_qty")
    def _onchange_rejected_qty(self):
        if self.requested_qty and self.rejected_qty is not None:
            if self.rejected_qty > self.requested_qty:
                self.rejected_qty = 0
                raise ValidationError(_("Rejected qty cannot exceed requested qty."))
            self.approved_qty = self.requested_qty - self.rejected_qty
