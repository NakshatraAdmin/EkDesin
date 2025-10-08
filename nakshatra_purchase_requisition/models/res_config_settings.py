from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pr_lead = fields.Float(
        related="company_id.pr_lead",
        string="Purchase Requisition Lead Time",
        readonly=False,
    )
