from odoo import models, _
from odoo.exceptions import UserError

class StockMove(models.Model):
    _inherit = 'stock.move'

    def write(self, vals):   # Greater than Demand Quantity
        for move in self:
            demand_qty = vals.get('product_uom_qty', move.product_uom_qty)
            qty = vals.get('quantity', move.quantity)

            if qty > demand_qty:
                raise UserError(_(
                    "Quantity (%s) cannot be greater than Demand Quantity (%s) for product %s."
                ) % (qty, demand_qty, move.product_id.display_name))

        return super().write(vals)
