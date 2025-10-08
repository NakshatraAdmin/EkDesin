from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _name = "approval.request"
    _description = "Approval Request"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True,
        copy=False,
        readonly=False,
        index="trigram",
        default=lambda self: _("New"),
    )
    request_owner_id = fields.Many2one("res.users")

    title = fields.Html(readonly=True)
    res_model = fields.Char(string="Resource Model")
    res_id = fields.Integer(string="Resource ID")
    priority = fields.Selection(
        [
            ("0", "Very Low"),
            ("1", "Low"),
            ("2", "Medium"),
            ("3", "High"),
            ("4", "Very High"),
        ],
        default="0",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_approve", "Under Approval"),
            ("approved", "Approved"),
            ("partially_approved", "Partially Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    approval_rule_id = fields.Many2one(
        "dynamic.approval.rule",
        readonly=True,
        string="Approval Rule",
        ondelete="cascade",
    )
    requested_date = fields.Datetime(string="Request Date", default=fields.Datetime.now)

    rejection_reason = fields.Text(tracking=True)

    deadline = fields.Date()

    description = fields.Text()

    is_show_approve_reject_button = fields.Boolean(
        compute="_compute_show_approve_reject_button"
    )

    approval_line_ids = fields.One2many(
        comodel_name="dynamic.request.assignee",
        inverse_name="approval_request_id",
        string="Approvers",
        readonly=True,
        tracking=True,
        help="Define the approvers for this request.",
    )
    assigned_approver_id = fields.Many2one(
        "res.users",
        string="Assigned Approver",
        readonly=True,
        help="The user currently assigned to handle this approval request.",
    )
    approver_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("skipped", "Skipped"),
        ],
        help="Current state of the approver for this request.",
    )
    model_id = fields.Many2one(
        "ir.model", ondelete="cascade", string="Model", tracking=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("approval.request") or "New"
                )
        return super().create(vals_list)

    def _compute_show_approve_reject_button(self):
        current_user = self.env.user
        for rec in self:
            rec = rec.sudo()
            rec.is_show_approve_reject_button = False
            for line in rec.approval_line_ids.sorted(key=lambda line: line.sequence):
                if line.primary_approval_state in ["approved", "rejected"] or (
                    line.primary_approval_state == "skipped"
                    and line.secondary_approval_state in ["approved", "rejected"]
                ):
                    continue

                if (
                    rec.state == "to_approve"
                    and rec.model_id.name != "Purchase Requisition"
                    and (
                        (
                            line.primary_approver == current_user
                            and line.primary_approval_state == "pending"
                        )
                        or (
                            line.secondary_approver == current_user
                            and line.primary_approval_state == "skipped"
                            and line.secondary_approval_state == "pending"
                        )
                    )
                ):
                    rec.is_show_approve_reject_button = True
                break

    def update_approver_and_state(self):
        for rec in self:
            if not rec.approval_line_ids:
                raise UserError(_("Please define approvers for this request."))
            for line in rec.approval_line_ids:
                if line.primary_approval_state == "pending":
                    rec.assigned_approver_id = line.primary_approver.id
                    rec.approver_state = "pending"
                    break
                elif (
                    line.secondary_approval_state == "pending"
                    and line.primary_approval_state not in ["approved", "rejected"]
                ):
                    rec.assigned_approver_id = line.secondary_approver.id
                    rec.approver_state = "pending"
                    break
                else:
                    rec.assigned_approver_id = False
                    rec.approver_state = False

            # If all lines are approved by either approver, set request to approved
            if all(
                line.primary_approval_state == "approved"
                or line.secondary_approval_state == "approved"
                for line in rec.approval_line_ids
            ):
                rec.state = "approved"
            elif any(
                line.primary_approval_state == "rejected"
                or line.secondary_approval_state == "rejected"
                for line in rec.approval_line_ids
            ):
                rec.state = "rejected"

    def check_for_approval(self, state):
        """Approve PR Lines and handle approval logic"""
        current_user = self.env.user
        # Get the PR from the first line
        if self.approval_line_ids:
            req = self.sudo()
            # Handle approval logic once
            if self.approval_rule_id.approval_level == "single":
                # Single level approval logic
                for approver_line in self.approval_line_ids:
                    if current_user.id == approver_line.primary_approver.id:
                        approver_line.write({"primary_approval_state": state})
                        self.update_approver_and_state()
                        self.send_notification(req, current_user, state)
                        break
                    elif current_user.id == approver_line.secondary_approver.id:
                        approver_line.write({"primary_approval_state": state})
                        self.update_approver_and_state()
                        self.send_notification(req, current_user, state)
                        break
                    else:
                        raise UserError(
                            _("You are not assigned in the current approval step.")
                        )
            else:
                # Multi-level approval logic
                approval_lines = self.approval_line_ids.sorted(key=lambda x: x.sequence)

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
                            approval_line.write({"primary_approval_state": state})
                            self.update_approver_and_state()
                            self.send_notification(req, current_user, state)
                            break
                        elif current_user.id == approval_line.secondary_approver.id:
                            if approval_line.primary_approval_state != "skipped":
                                raise UserError(
                                    _(
                                        "Waiting for primary approver to approve/skipped before you can approve."
                                    )
                                )

                            approval_line.write({"secondary_approval_state": state})
                            self.send_notification(req, current_user, state)
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

    def send_notification(self, req, action_by, state):
        """Send in-app notification and plain email when PR approval step is taken"""
        approval_request = req
        if not approval_request:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref("dynamic_approval_rule.action_approval_request")
        action_url = (
            f"{base_url}/web#id={approval_request.id}"
            f"&action={action.id}"
            f"&model=approval.request"
            f"&view_type=form"
        )

        # Message body for both email and in-app
        message = (
            f"Approval Request <b>{approval_request.name}</b> has been <b>{state.upper()}</b> by <b>{action_by.name}</b>.<br/>"
            f"<a href='{action_url}' target='_blank'>View Request</a>"
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

    def action_approve(self):
        self.check_for_approval("approved")

    def action_reject(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Reject Reason",
            "res_model": "approval.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }


class RequestAssignee(models.Model):
    _name = "dynamic.request.assignee"
    _description = "Approver for Rule"
    _order = "sequence, primary_approver"

    approval_request_id = fields.Many2one(
        "approval.request", string="Approver Line", ondelete="cascade"
    )
    sequence = fields.Integer(
        default=0,
        help="Determines the order of approvers. Lower numbers are processed first.",
    )

    # primary approver settings
    primary_approver = fields.Many2one(
        "res.users",
        string="Approver",
        required=True,
        help="Primary approver for the rule. This user will be notified for approval requests.",
    )
    primary_response_duration = fields.Integer(
        string="Response Duration", help="Time allowed for approvers to respond"
    )
    primary_response_duration_unit = fields.Selection(
        [("hours", "Hours"), ("days", "Days")],
        string="Duration Unit",
        default="hours",
        help="Unit of time for response duration",
    )
    primary_reminder_count = fields.Integer(
        string="Number of Reminders",
        help="Number of reminders to send if no response is received",
    )
    primary_reminder_interval = fields.Integer(
        string="Reminder Interval (Hours)", help="Interval in hours between reminders"
    )
    primary_post_reminder_action = fields.Selection(
        [
            ("approve", "Auto Approve"),
            ("reject", "Auto Reject"),
            ("reallocate", "Reallocate to Another User"),
        ],
        string="Post Reminder Action",
        help="Action to take after reminders are sent if no response is received",
    )
    primary_designation = fields.Char(
        string="Designation", help="Designation of the approver, if applicable."
    )
    primary_approval_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("skipped", "Skipped"),
        ],
        string="Approval Stage",
        default="pending",
    )
    primary_reminder_sent = fields.Integer(string="Reminders Sent", default=0)
    primary_last_reminder_sent = fields.Datetime(string="Last Reminder Sent")

    # Secondary approver settings
    secondary_approver = fields.Many2one(
        "res.users",
        help="Secondary approver if the primary is unavailable or does not respond in time.",
    )
    secondary_response_duration = fields.Integer(
        help="Time allowed for approvers to respond",
    )
    secondary_response_duration_unit = fields.Selection(
        [("hours", "Hours"), ("days", "Days")],
        string="Secondary Duration Unit",
        default="hours",
        help="Unit of time for response duration",
    )
    secondary_reminder_count = fields.Integer(
        string="Secondary Number of Reminders",
        help="Number of reminders to send if no response is received",
    )
    secondary_reminder_interval = fields.Integer(
        string="Secondary Reminder Interval (Hours)",
        help="Interval in hours between reminders",
    )
    secondary_post_reminder_action = fields.Selection(
        [("approve", "Auto Approve"), ("reject", "Auto Reject")],
        help="Action to take after reminders are sent if no response is received",
    )
    secondary_designation = fields.Char(
        string="Secondary User Designation",
        help="Designation of the approver, if applicable.",
    )

    secondary_approval_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("skipped", "Skipped"),
        ],
        string="Secondary Approval Stage",
        default="pending",
    )
    secondary_reminder_sent = fields.Integer(default=0)
    secondary_last_reminder_sent = fields.Datetime()
