from odoo import api, models, fields


class StockMove(models.Model):
    _inherit = "stock.move"

    wastage = fields.Float()
