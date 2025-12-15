from odoo import models, fields

class SaleCancelReasonWizard(models.TransientModel):
    _name = 'sale.cancel.reason.wizard'
    _description = 'Sale Order Cancel Reason'

    reason = fields.Text(string="Reason", required=True)

    def action_confirm_cancel(self):
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        sale_order.write({
            'cancel_reason': self.reason
        })
        sale_order.action_cancel()
