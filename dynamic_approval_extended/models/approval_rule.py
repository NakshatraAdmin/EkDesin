from odoo import models, fields, api, _

class DynamicApprovalRule(models.Model):
    _inherit = "dynamic.approval.rule"

    approval_type = fields.Selection(
        selection_add=[("parallel", "Parallel")],
        ondelete={"parallel": "set default"},
        readonly=False,
    )
