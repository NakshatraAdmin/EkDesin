from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    pr_lead = fields.Float(string="Purchase Requisition Lead time", default="1.0")
