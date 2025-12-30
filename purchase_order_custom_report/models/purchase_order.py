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
    doc_no = fields.Char(
        string="Document No",
        default="EKD/STR/FR/01"
    )

    revision_no = fields.Char(
        string="Revision No",
        default="0"
    )

    revision_date = fields.Date(
        string="Revision Date",
        default=fields.Datetime.now()
    )
    reference_date = fields.Date(
        string="Reference No & Date :",
        default=fields.Datetime.now()
    )
    terms_of_delivery = fields.Char("Terms Of Delivery")
    

    @api.depends('amount_total')
    def _compute_roundoff(self):
        for order in self:
            total = Decimal(str(order.amount_total))

            # ₹1 rounding – SAME AS INVOICE
            rounded_total = total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

            order.amount_roundoff = float(rounded_total - total)
            order.amount_total_rounded = float(rounded_total)

    def create(self, vals):
        # Create the RFQ
        order = super(PurchaseOrder, self).create(vals)

        # Check if the RFQ is in 'draft' state and confirm it automatically
        if order.state == 'draft':
            order.button_confirm()  # This will confirm the RFQ and create the Purchase Order
        
        return order

