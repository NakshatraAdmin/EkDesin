from odoo import api, fields, models
from decimal import Decimal, ROUND_HALF_UP

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    amount_roundoff = fields.Monetary(
        string="Round Off",
        compute="_compute_roundoff",
        store=True,
    )
    amount_total_rounded = fields.Monetary(
        string="Total",
        compute="_compute_roundoff",
        store=True,
    )

    @api.depends('amount_total')
    def _compute_roundoff(self):
        for order in self:
            total = Decimal(str(order.amount_total))

            # ₹1 rounding – SAME AS INVOICE
            rounded_total = total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

            order.amount_roundoff = float(rounded_total - total)
            order.amount_total_rounded = float(rounded_total)
