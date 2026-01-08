from odoo import models, fields

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    height = fields.Float()
    length = fields.Float()
    width = fields.Float()

    actual_height = fields.Float()
    actual_length = fields.Float()
    actual_width = fields.Float()

