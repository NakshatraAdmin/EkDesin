from odoo import models, fields

class StockQuant(models.Model):
    _inherit = "stock.quant"

    product_categ_id = fields.Many2one(related='product_tmpl_id.categ_id', store=True)
