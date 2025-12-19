from odoo import models, fields, api
from odoo.exceptions import UserError

class SaleCancelReasonWizard(models.TransientModel):
    _name = 'sale.cancel.reason.wizard'
    _description = 'Sale Cancel Reason Wizard'

    order_id = fields.Many2one('sale.order', required=True)
    cancel_reason_id = fields.Many2one(
        'sale.cancel.reason',
        string='Reason',
        required=True,
    )
    note = fields.Text(string='Remark')

    def action_confirm_cancel(self):
        self.ensure_one()

        order = self.order_id
        order.write({
            'cancel_reason_id': self.cancel_reason_id.id,
            'cancel_reason_note': self.note,
        })

        order.action_cancel()
