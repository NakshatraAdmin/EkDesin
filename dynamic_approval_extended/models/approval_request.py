from odoo import _, models
from odoo.exceptions import UserError
from markupsafe import Markup


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    def _is_parallel_approval(self):
        self.ensure_one()
        return self.approval_rule_id.approval_type == "parallel"

    def _get_parallel_pending_slot(self, user):
        self.ensure_one()
        for line in self.approval_line_ids.sorted(
            key=lambda approver: approver.sequence
        ):
            if (
                line.primary_approver.id == user.id
                and line.primary_approval_state == "pending"
            ):
                return line, "primary"
            if (
                line.secondary_approver.id == user.id
                and line.secondary_approval_state == "pending"
            ):
                return line, "secondary"
        return self.env["dynamic.request.assignee"], False

    def _get_parallel_pending_approver_users(self):
        users = self.env["res.users"]
        for request in self:
            if request.state != "to_approve":
                continue
            for line in request.approval_line_ids:
                if (
                    line.primary_approver
                    and line.primary_approval_state == "pending"
                ):
                    users |= line.primary_approver
                if (
                    line.secondary_approver
                    and line.secondary_approval_state == "pending"
                ):
                    users |= line.secondary_approver
        return users

    def _has_parallel_pending_action(self, user):
        self.ensure_one()
        if self.state != "to_approve":
            return False
        if self.model_id.name == "Purchase Requisition":
            return False

        line, approval_slot = self._get_parallel_pending_slot(user)
        return bool(line and approval_slot)

    def _get_parallel_approval_state(self):
        self.ensure_one()
        has_approved = any(
            line.primary_approval_state == "approved"
            or line.secondary_approval_state == "approved"
            for line in self.approval_line_ids
        )
        if has_approved:
            return "approved"

        has_rejected = any(
            line.primary_approval_state == "rejected"
            or line.secondary_approval_state == "rejected"
            for line in self.approval_line_ids
        )
        if has_rejected:
            return "rejected"

        return "to_approve"

    def _apply_parallel_approval_state(self):
        for request in self:
            if not request.approval_line_ids:
                raise UserError(_("Please define approvers for this request."))

            approval_state = request._get_parallel_approval_state()
            if approval_state in ("approved", "rejected"):
                request.state = approval_state
                request.assigned_approver_id = False
                request.approver_state = approval_state
                continue

            pending_users = request._get_parallel_pending_approver_users()
            request.assigned_approver_id = (
                pending_users[:1].id if pending_users else False
            )
            request.approver_state = "pending" if pending_users else False

    def _compute_show_approve_reject_button(self):
        res = super()._compute_show_approve_reject_button()
        current_user = self.env.user
        for request in self:
            if request._is_parallel_approval():
                request.is_show_approve_reject_button = (
                    request._has_parallel_pending_action(current_user)
                )
        return res

    def update_approver_and_state(self):
        parallel_requests = self.filtered(
            lambda request: request._is_parallel_approval()
        )
        parallel_requests._apply_parallel_approval_state()
        res = super().update_approver_and_state()
        parallel_requests._apply_parallel_approval_state()
        return res

    def check_for_approval(self, state):
        for request in self:
            if not request._is_parallel_approval():
                super(ApprovalRequest, request).check_for_approval(state)
                continue

            if request.state != "to_approve":
                raise UserError(_("This approval request is not waiting for approval."))
            if not request.approval_line_ids:
                raise UserError(_("Please define approvers for this request."))

            current_user = request.env.user
            approval_line, approval_slot = request._get_parallel_pending_slot(
                current_user
            )
            if not approval_line:
                raise UserError(_("You are not assigned to this approval request."))

            approval_line.write({f"{approval_slot}_approval_state": state})
            request.update_approver_and_state()
            request.send_notification(request.sudo(), current_user, state)

    def send_notification(self, req, action_by, state):
        if not self._is_parallel_approval():
            return super().send_notification(req, action_by, state)

        approval_request = req
        if not approval_request:
            return None

        recipients = approval_request.request_owner_id
        if not recipients:
            return None

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref("dynamic_approval_rule.action_approval_request")
        action_url = (
            f"{base_url}/web#id={approval_request.id}"
            f"&action={action.id}"
            f"&model=approval.request"
            f"&view_type=form"
        )
        message = (
            f"Approval Request <b>{approval_request.name}</b> has been "
            f"<b>{state.upper()}</b> by <b>{action_by.name}</b>.<br/>"
            f"<a href='{action_url}' target='_blank'>View Request</a>"
        )

        for user in recipients:
            if approval_request.approval_rule_id.notify_in_app and user.partner_id:
                self.env["mail.thread"].sudo().message_notify(
                    body=Markup(message),
                    subject="Approval Update",
                    partner_ids=[user.partner_id.id],
                    res_id=approval_request.id,
                    record_name=approval_request.name,
                    email_layout_xmlid="mail.mail_notification_light",
                )

            if (
                approval_request.approval_rule_id.notify_email
                and user.email
                and user.partner_id
            ):
                self.env["mail.mail"].sudo().create(
                    {
                        "subject": f"Approval Update - {approval_request.name}",
                        "body_html": f"<p>{message}</p>",
                        "email_to": user.email,
                        "auto_delete": True,
                        "author_id": self.env.user.partner_id.id,
                    }
                ).send()

        return None
