from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.http import request
from datetime import timedelta
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class DynamicApprovalRule(models.Model):
    _name = "dynamic.approval.rule"
    _description = "Dynamic Approval Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True,
        copy=False,
        readonly=False,
        index="trigram",
        default=lambda self: _("New"),
    )
    title = fields.Char(required=True, tracking=True)
    available_model_ids = fields.Many2many("ir.model")
    model_id = fields.Many2one(
        "ir.model",
        ondelete="cascade",
        string="Model",
        required=True,
        tracking=True,
        domain="[('id', 'in', available_model_ids)]",
    )
    model_name = fields.Char(compute="_compute_model_name", store=True)
    domain = fields.Char(string="Trigger Condition (domain)", tracking=True)

    is_active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True,
        help="Enable or disable this approval rule. Inactive rules will not be applied.",
    )
    # Section 1: Approval Flow
    approval_level = fields.Selection(
        [("single", "Single Level"), ("multi", "Multi Level")],
        default="single",
        required=True,
        help="Select the approval level for this workflow",
    )

    approval_type = fields.Selection(
        [("sequential", "Sequential")],  # staging ("parallel", "Parallel")
        default="sequential",
        required=True,
        help="Select the type of approval flow",
    )

    approval_line_ids = fields.One2many(
        comodel_name="dynamic.rule.assignee",
        inverse_name="approval_rule_id",
        string="Approvers",
        copy=True,
        readonly=False,
        help="Define the approvers for this approval type. Each line represents an approver.",
    )

    # Section 3: Notification
    notify_email = fields.Boolean(
        string="Notify by Email",
        tracking=True,
        help="Send email notifications to approvers",
    )
    notify_in_app = fields.Boolean(
        string="Notify in Odoo",
        default=True,
        tracking=True,
        help="Send in-app notifications to approvers",
    )

    @api.model
    def default_get(self, fields_list):
        # EXTENDS base
        defaults = super().default_get(fields_list)
        available_model_ids = self._get_model_domain()
        defaults["available_model_ids"] = [(6, 0, available_model_ids)]

        if "approval_line_ids" in fields_list and not defaults.get("approval_line_ids"):
            defaults["approval_line_ids"] = [(0, 0, {})]

        return defaults

    @api.model
    def _get_model_domain(self):
        allowed_models = []
        group_ids = request.env.user.groups_id.ids
        acls = (
            self.env["ir.model.access"]
            .sudo()
            .search(
                [
                    ("group_id", "in", group_ids),
                    ("perm_create", "=", True),
                    ("perm_write", "=", True),
                ]
            )
        )
        for acl in acls:
            model = acl.model_id
            if model and model.model:
                allowed_models.append(model.model)
        allowed_model_ids = (
            self.env["ir.model"].sudo().search([("model", "in", allowed_models)])
        )
        return allowed_model_ids.ids

    # get model name from model_id
    @api.depends("model_id")
    def _compute_model_name(self):
        for rec in self:
            rec.model_name = rec.model_id.model or ""

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("dynamic.approval.rule")
                    or "New"
                )

                # Check for duplicate rules with same model and state
                model_id = vals.get("model_id")
                new_domain_str = vals.get("domain", "[]")

                if model_id:
                    # Normalize the new domain
                    try:
                        new_domain = safe_eval(new_domain_str) if new_domain_str else []
                    except Exception:
                        raise UserError(_("Invalid domain syntax."))

                    # Extract state value from new domain
                    new_state = self._extract_state_from_domain(new_domain)
                    # Search for existing rules with the same model
                    existing_rules = self.search(
                        [("model_id", "=", model_id), ("is_active", "=", True)]
                    )
                    if existing_rules:
                        for rule in existing_rules:
                            try:
                                existing_domain = (
                                    safe_eval(rule.domain) if rule.domain else []
                                )
                                existing_state = self._extract_state_from_domain(
                                    existing_domain
                                )
                                if (
                                    new_state
                                    and existing_state
                                    and new_state == existing_state
                                ):
                                    raise UserError(
                                        _(
                                            "A rule already exists for this model with status '%s'. Only one rule per state is allowed."
                                        )
                                        % new_state
                                    )

                                # If both domains are empty (no state condition), also block duplicate
                                if not new_state and not existing_state:
                                    raise UserError(
                                        _(
                                            "A rule already exists for this model without state condition."
                                        )
                                    )

                            except Exception as e:
                                if isinstance(e, UserError):
                                    raise e
                                continue

            if not vals.get("approval_line_ids"):
                raise ValidationError(
                    _("Please define at least one approver in the rule.")
                )

            return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if not rec.approval_line_ids:
                raise ValidationError(
                    _("At least one approver must be defined in the rule.")
                )
        return res

    def _extract_state_from_domain(self, domain):
        """
        Extract state value from domain conditions.
        Returns the state value if found, None otherwise.
        """
        if not domain:
            return None

        for condition in domain:
            if isinstance(condition, (list, tuple)) and len(condition) >= 3:
                field, operator, value = condition[0], condition[1], condition[2]

                # Check if this condition is for 'state' field
                if field == "state" and operator == "=":
                    return value

        return None

    @api.onchange(
        "response_duration",
        "response_duration_unit",
        "reminder_count",
        "reminder_interval",
    )
    @api.constrains("approval_level", "approval_line_ids")
    def _check_single_level_line_limit(self):
        if self.approval_level == "single" and len(self.approval_line_ids) > 1:
            raise ValidationError(
                _("Only one approver line is allowed in single-level approval.")
            )

    # @api.onchange("approval_level")
    # def _onchange_approval_level(self):
    #     if self.approval_level == "multi" and self.model_id.model == "sale.order":
    #         raise UserError(_("Multi-level approval is not supported for Sale Orders."))

    def check_approval_required_for_record(self, record):
        """
        Check if this rule applies to the given record.
        """
        if not self.domain:
            return True
        domain = safe_eval(self.domain or "[]", {"uid": record.env.uid})
        return record.search_count([("id", "=", record.id)] + domain) > 0

    @api.model
    def is_approval_required(cls, env, model_name, record_id):
        """
        Check if any rule applies to a specific record, given model name and ID.
        """
        rules = env["dynamic.approval.rule"].search([("model_name", "=", model_name)])
        record = env[model_name].browse(record_id)
        return any(rule.check_approval_required_for_record(record) for rule in rules)

    @api.model
    def create_approval_request(self, record):
        base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
        record_url = (
            f"{base_url}/web#id={record.id}&model={record._name}&view_type=form"
        )

        rules = record.env["dynamic.approval.rule"].search(
            [
                ("model_id.model", "=", record._name),
                ("is_active", "=", True),
            ]
        )

        rule = None
        for r in rules:
            domain = []
            if r.domain:
                try:
                    domain = safe_eval(r.domain)
                except Exception as e:
                    _logger.warning(f"Invalid domain in rule {r.name}: {e}")
                    continue  # Skip this rule if domain is invalid

            # Check state condition match (if any)
            state_matches = True
            for condition in domain:
                if (
                    isinstance(condition, (list, tuple))
                    and condition[0] == "state"
                    and condition[1] == "="
                ):
                    if record.state != condition[2]:
                        state_matches = False
                        break

            if state_matches:
                rule = r  # found first matching rule
                break

        if not rule:
            _logger.warning(
                f"No approval rule found for model {record._name} with matching state."
            )
            raise UserError(
                _("No valid approval rule defined for model %s") % record._name
            )

        # Search for existing approval request
        approval_request = record.env["approval.request"].search(
            [
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
                ("approval_rule_id", "=", rule.id),
            ],
            limit=1,
        )

        # Create new if not found
        if not approval_request:
            approval_request = record.env["approval.request"].create(
                {
                    "title": f'Approval for <a href="{record_url}">{record.display_name}</a>',
                    "request_owner_id": record.user_id.id
                    if hasattr(record, "user_id")
                    else record.env.uid,
                    "approval_rule_id": rule.id,
                    "res_model": record._name,
                    "res_id": record.id,
                    "state": "to_approve",
                    "model_id": rule.model_id.id,
                }
            )

        # Remove old lines
        approval_request.approval_line_ids.unlink()

        # Prepare new lines
        lines_to_create = []
        for rule_line in rule.approval_line_ids.sorted(key=lambda line: line.sequence):
            lines_to_create.append(
                (
                    0,
                    0,
                    {
                        "sequence": rule_line.sequence,
                        "primary_approver": rule_line.primary_approver.id,
                        "primary_response_duration": rule_line.primary_response_duration,
                        "primary_response_duration_unit": rule_line.primary_response_duration_unit,
                        "primary_reminder_count": rule_line.primary_reminder_count,
                        "primary_reminder_interval": rule_line.primary_reminder_interval,
                        "primary_post_reminder_action": rule_line.primary_post_reminder_action,
                        "primary_designation": rule_line.primary_designation,
                        "primary_approval_state": "pending",
                        "primary_reminder_sent": 0,
                        "primary_last_reminder_sent": False,
                        "secondary_approver": rule_line.secondary_approver.id,
                        "secondary_response_duration": rule_line.secondary_response_duration,
                        "secondary_response_duration_unit": rule_line.secondary_response_duration_unit,
                        "secondary_reminder_count": rule_line.secondary_reminder_count,
                        "secondary_reminder_interval": rule_line.secondary_reminder_interval,
                        "secondary_post_reminder_action": rule_line.secondary_post_reminder_action,
                        "secondary_designation": rule_line.secondary_designation,
                        "secondary_approval_state": "pending",
                        "secondary_reminder_sent": 0,
                        "secondary_last_reminder_sent": False,
                    },
                )
            )

        # Write lines to approval request
        if lines_to_create:
            approval_request.write(
                {
                    "approval_line_ids": lines_to_create,
                }
            )

        # Link to source record if applicable
        if hasattr(record, "approval_request_id"):
            record.approval_request_id = approval_request.id

        # Set assigned approver
        if approval_request.approval_line_ids:
            assigned_approver_id = approval_request.approval_line_ids[
                0
            ].primary_approver.id
            approval_request.write(
                {
                    "assigned_approver_id": assigned_approver_id,
                    "approver_state": "pending",
                }
            )

        return approval_request

    @api.model
    def process_dynamic_approval_reminders(self):
        requests = self.env["approval.request"].search(
            [("state", "not in", ["approved", "cancelled", "rejected"])]
        )
        now = fields.Datetime.now()

        for approval_request in requests:
            rule = approval_request.approval_rule_id
            if not rule or not approval_request.approval_line_ids:
                continue

            for line in approval_request.approval_line_ids.sorted(
                key=lambda line: line.sequence
            ):
                # If primary already approved → move to next
                if (
                    line.primary_approval_state == "approved"
                    or line.secondary_approval_state == "approved"
                ):
                    _logger.info(
                        f"Skipping reminders for {line.primary_approver.name} as already approved. #PR_ID: {line.approval_request_id.res_id}"
                    )
                    continue

                # Primary reminder logic
                if line.primary_approval_state == "pending" and line.primary_approver:
                    if self._should_remind(
                        line.primary_last_reminder_sent,
                        line.primary_reminder_interval,
                        now,
                    ):
                        _logger.info(
                            f"Primary Reminder sent {line.primary_last_reminder_sent} for Approval Req: {approval_request.name}"
                            f"\n Primary Reminder Interval {line.primary_reminder_interval} for Approval Req: {approval_request.name}"
                        )

                        if line.primary_reminder_sent < (
                            line.primary_reminder_count or 0
                        ):
                            line.write(
                                {
                                    "primary_reminder_sent": line.primary_reminder_sent
                                    + 1,
                                    "primary_last_reminder_sent": now,
                                }
                            )
                            self._send_notification(
                                line.primary_approver, approval_request
                            )
                            _logger.info(
                                f"Primary reminder #{line.primary_reminder_sent} sent to {line.primary_approver.name}"
                            )
                        else:
                            self._do_post_action(approval_request, line, "primary")
                    break  # Only process one line at a time

                # Secondary reminder logic (only if primary not approved and secondary exists)
                if (
                    line.secondary_approver
                    and line.primary_approval_state != "approved"
                ):
                    if line.secondary_approval_state == "pending":
                        if self._should_remind(
                            line.secondary_last_reminder_sent,
                            line.secondary_reminder_interval,
                            now,
                        ):
                            _logger.info(
                                f"Secondary Reminder sent {line.secondary_last_reminder_sent} for Approval Req: {approval_request.name}"
                                f"\n Secondary Reminder Interval {line.secondary_reminder_interval} for Approval Req: {approval_request.name}"
                            )

                            if line.secondary_reminder_sent < (
                                line.secondary_reminder_count or 0
                            ):
                                line.write(
                                    {
                                        "secondary_reminder_sent": line.secondary_reminder_sent
                                        + 1,
                                        "secondary_last_reminder_sent": now,
                                    }
                                )
                                self._send_notification(
                                    line.secondary_approver, approval_request
                                )
                                _logger.info(
                                    f"Secondary reminder #{line.secondary_reminder_sent} sent to {line.secondary_approver.name}"
                                )
                            else:
                                self._do_post_action(
                                    approval_request, line, "secondary"
                                )
                    break  # Only process one line at a time

                break  # Stop after handling the first incomplete line

    def _should_remind(self, last_reminder, interval_hours, now):
        interval = interval_hours or 0
        _logger.info(f"Processing last now {now}")
        _logger.info(f"Processing last {last_reminder}")

        if not last_reminder:
            return True
        return now >= last_reminder + timedelta(minutes=interval)

    def _send_notification(self, user, approval_request):
        if not user or not user.partner_id:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref(
            "nakshatra_purchase_requisition.action_purchase_requisition_line"
        )
        action_url = f"{base_url}/web#action={action.id}&model=nakshatra.purchase.requisition.line&view_type=list"
        pr = self.env[approval_request.res_model].sudo().browse(approval_request.res_id)

        body = Markup(
            f"Reminder: Please approve PR <b>{pr.name}</b>.<br/>"
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
                "subject": f"Reminder: Approval Needed for PR - {pr.name}",
                "body_html": f"<p>{body}</p>",
                "email_to": user.email,
                "auto_delete": True,
                "author_id": user.partner_id.id,
            }
            approval_request.env["mail.mail"].create(mail_vals).send()

    def _do_post_action(self, request, line, role):
        if role == "primary":
            action = line.primary_post_reminder_action
            field = "primary_approval_state"
            user = line.primary_approver
        else:
            action = line.secondary_post_reminder_action
            field = "secondary_approval_state"
            user = line.secondary_approver

        if not action or not user:
            return

        if action == "approve":
            line.write({field: "approved"})
            request.update_approver_and_state()
            _logger.info(
                f"{role.capitalize()} approver {user.name} auto-approved for request {request.name}"
            )
        elif action == "reject":
            line.write({field: "rejected"})
            request.update_approver_and_state()
            _logger.info(
                f"{role.capitalize()} approver {user.name} auto-rejected for request {request.name}"
            )
        elif action == "reallocate":
            line.write({field: "skipped"})
            request.update_approver_and_state()
            _logger.info(
                f"{role.capitalize()} reallocation requested (not implemented) for {user.name}"
            )

        # Update Approval Request , PR Or PR lines status update
        approval_lines = request.approval_line_ids

        has_rejected = any(
            line.primary_approval_state == "rejected"
            or line.secondary_approval_state == "rejected"
            for line in approval_lines
        )

        has_approved = all(
            line.primary_approval_state == "approved"
            or line.secondary_approval_state == "approved"
            for line in approval_lines
        )

        if has_rejected:
            pr = self.env[request.res_model].sudo().browse(request.res_id)
            request.write({"state": "rejected"})
            if pr._name == "nakshatra.purchase.requisition":
                pr.line_ids.write({"item_status": "rejected"})
                pr.write({"state": "rejected"})
            _logger.info(f"Approval Request {request.name} rejected by {user.name}")

        if has_approved:
            pr = self.env[request.res_model].sudo().browse(request.res_id)
            request.write({"state": "approved"})
            if pr._name == "nakshatra.purchase.requisition":
                pr.line_ids.write({"item_status": "approved"})
                pr.write({"state": "approved"})
            _logger.info(f"Approval Request {request.name} approved by {user.name}")

    @api.constrains("is_active", "model_id")
    def _onchange_check_existing_active_rule(self):
        if self.is_active and self.model_id:
            existing = self.env["dynamic.approval.rule"].search(
                [
                    ("model_id", "=", self.model_id.id),
                    ("is_active", "=", True),
                    ("id", "!=", self.id),  # exclude current record
                ],
                limit=1,
            )

            if existing:
                raise ValidationError(
                    _("An active approval rule already exists for this model.")
                )


# assignees for the approval rule
class RuleAssignee(models.Model):
    _name = "dynamic.rule.assignee"
    _description = "Approver for Rule"
    _order = "sequence, primary_approver"

    approval_rule_id = fields.Many2one(
        "dynamic.approval.rule", string="Approver Line", ondelete="cascade"
    )

    sequence = fields.Integer(
        default=1,
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
        string="Response Duration",
        default=1,
        help="Time allowed for approvers to respond",
    )
    primary_response_duration_unit = fields.Selection(
        [("hours", "Hours"), ("days", "Days")],
        string="Duration Unit",
        default="hours",
        help="Unit of time for response duration",
    )
    primary_reminder_count = fields.Integer(
        string="Number of Reminders",
        default=60,
        help="Number of reminders to send if no response is received",
    )
    primary_reminder_interval = fields.Integer(
        string="Reminder Interval (Min)",
        default=1,
        help="Interval in minutes between reminders",
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
        default=1,
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
        default=60,
        help="Number of reminders to send if no response is received",
    )
    secondary_reminder_interval = fields.Integer(
        string="Secondary Reminder Interval (Min)",
        default=1,
        help="Interval in minutes between reminders",
    )
    secondary_post_reminder_action = fields.Selection(
        [("approve", "Auto Approve"), ("reject", "Auto Reject")],
        help="Action to take after reminders are sent if no response is received",
    )
    secondary_designation = fields.Char(
        string="Secondary User Designation",
        help="Designation of the approver, if applicable.",
    )

    @api.onchange("primary_approver")
    def _check_single_level_line_limit(self):
        for rec in self:
            lines = rec.approval_rule_id.approval_line_ids

            # Filter out empty/incomplete lines
            valid_lines = lines.filtered(
                lambda line: line.primary_approver or line.secondary_approver
            )

            if rec.approval_rule_id.approval_level == "single" and len(valid_lines) > 1:
                raise ValidationError(
                    _("Only one approver line is allowed in single-level approval.")
                )

    @api.onchange(
        "primary_response_duration",
        "primary_response_duration_unit",
        "primary_reminder_interval",
    )
    def _onchange_validate_primary_reminder_duration(self):
        for rec in self:
            rec._compute_reminder_count("primary")

    @api.onchange(
        "secondary_response_duration",
        "secondary_response_duration_unit",
        "secondary_reminder_interval",
    )
    def _onchange_validate_secondary_reminder_duration(self):
        for rec in self:
            rec._compute_reminder_count("secondary")

    def _compute_reminder_count(self, role):
        duration = getattr(self, f"{role}_response_duration") or 0
        unit = getattr(self, f"{role}_response_duration_unit")
        interval = getattr(self, f"{role}_reminder_interval") or 0

        # Convert duration to minutes
        if unit == "days":
            duration_minutes = duration * 24 * 60
        elif unit == "hours":
            duration_minutes = duration * 60
        else:
            duration_minutes = 0

        if interval <= 0:
            setattr(self, f"{role}_reminder_count", 0)
            return

        if duration_minutes < interval:
            setattr(self, f"{role}_reminder_count", 0)
            raise UserError(
                _(
                    f"{role.capitalize()} reminder interval is too large for the selected response duration. "
                    f"Please reduce the interval or increase the duration."
                )
            )

        reminder_count = duration_minutes // interval
        setattr(self, f"{role}_reminder_count", reminder_count)

    @api.onchange("primary_response_duration_unit")
    def _onchange_primary_response_duration_unit(self):
        if self.primary_response_duration_unit:
            self.secondary_response_duration_unit = self.primary_response_duration_unit
