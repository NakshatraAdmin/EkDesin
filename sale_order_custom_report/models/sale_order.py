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

    cancel_reason_id = fields.Many2one(
        'sale.cancel.reason',
        string='Cancel Reason',
        readonly=True,
        copy=False,
    )
    cancel_reason_note = fields.Text(
        string='Cancel Reason Note',
        readonly=True,
        copy=False,
    )
    sale_comment = fields.Html(
        string="Sale Comment",
        help="This comment will appear in Sale Order PDF"
    )
    
    @api.depends('amount_total')
    def _compute_roundoff(self):
        for order in self:
            total = Decimal(str(order.amount_total))

            # ₹1 rounding – SAME AS INVOICE
            rounded_total = total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

            order.amount_roundoff = float(rounded_total - total)
            order.amount_total_rounded = float(rounded_total)


    # def action_confirm_cancel(self):
    #     sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
    #     sale_order.write({
    #         'cancel_reason': self.reason
    #     })
    #     sale_order.action_cancel()


    def action_open_cancel_reason(self):
        self.ensure_one()
        return {
            'name': 'Cancel Sale Order',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.cancel.reason.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
            }
        }



class SaleCancelReason(models.Model):
    _name = 'sale.cancel.reason'
    _description = 'Sale Cancel Reason'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sale_comment = fields.Html(
        string="Sale Comment",
        help="This comment will appear in Sale Order PDF"
    )


class KPIProvider(models.Model):
    _name = 'kpi.provider'
    _description = 'KPI Provider'

    # Define the fields for the model
    name = fields.Char(string='Name')
    description = fields.Text(string='Description')