from odoo import models,fields


class StockLot(models.Model):
    _inherit = 'stock.lot'

    length = fields.Float(
        related='product_id.product_tmpl_id.length',
        string='Length',
        store=True
    )
    width = fields.Float(
        related='product_id.product_tmpl_id.width',
        string='Width',
        store=True
    )
    height = fields.Float(
        related='product_id.product_tmpl_id.height',
        string='Height',
        store=True
    )
