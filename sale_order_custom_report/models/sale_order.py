from odoo import models, fields,api, _
from markupsafe import Markup
from odoo.exceptions import UserError
from decimal import Decimal, ROUND_HALF_UP



class SaleOrder(models.Model):
    _inherit = "sale.order"

    amount_roundoff = fields.Monetary(
        string="Round Off",
        compute="_compute_roundoff",
        store=True,
    )
    amount_total_rounded = fields.Monetary(
        string="Final Amount",
        compute="_compute_roundoff",
        store=True,
    )

    cancel_reason = fields.Text(string="Cancel Reason", readonly=True)

    @api.depends('amount_total')
    def _compute_roundoff(self):
        for order in self:
            total = Decimal(str(order.amount_total))

            # ₹1 rounding – SAME AS INVOICE
            rounded_total = total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

            order.amount_roundoff = float(rounded_total - total)
            order.amount_total_rounded = float(rounded_total)


    def action_confirm_cancel(self):
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        sale_order.write({
            'cancel_reason': self.reason
        })
        sale_order.action_cancel()