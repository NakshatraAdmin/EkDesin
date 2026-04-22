from odoo import models, fields


class DynamicApprovalRule(models.Model):
    _inherit = "dynamic.approval.rule"

    approval_type = fields.Selection(
        selection_add=[("parallel", "Parallel")],
        ondelete={"parallel": "set default"},
        readonly=False,
    )

    def create_approval_request(self, record):
        approval_request = super().create_approval_request(record)
        if approval_request.approval_rule_id.approval_type == "parallel":
            approval_request._apply_parallel_approval_state()
            approval_request._send_parallel_initial_notification(record)
        return approval_request
