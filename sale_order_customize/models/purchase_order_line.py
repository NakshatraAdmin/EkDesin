from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    discount_type = fields.Selection(
        [
            ("percent", "percent"),
            ("amount", "Amount"),
        ],
        default="percent",
        string="Discount Type",
    )

    discount_amount = fields.Float(string="Discount Amount")

    @api.onchange(
        "discount_type",
        "discount_amount",
        "price_unit",
        "product_qty"
    )
    def _onchange_discount_amount(self):
        for line in self:
            if line.discount_type == "amount":
                total = line.price_unit * line.product_qty
                if total > 0:
                    line.discount = (line.discount_amount / total) * 100
                else:
                    line.discount = 0.0
            else:
                line.discount_amount = 0.0
