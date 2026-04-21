from odoo import api, models, fields


class MRP(models.Model):
    _inherit = "mrp.production"

    state = fields.Selection(selection_add=[("confirmed", "Not Started")])
