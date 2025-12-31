from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    prepared_by_id = fields.Many2one(
        'res.users',
        string="Prepared By",
        default=lambda self: self.env.user
    )

    approved_by_id = fields.Many2one(
        'res.users',
        string="Approved By"
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

    invoice_no = fields.Char(
        string="Invoice No",
        
    )

    invoice_date = fields.Date(
        string="Invoice Date",
        default=fields.Datetime.now()
    )
    terms_of_delivery= fields.Char(
        string="Terms Of Delivery"
        
    )
    project_id = fields.Many2one("project.project", tracking=True)

class StockMove(models.Model):
    _inherit = 'stock.move'

    reject_qty = fields.Float(
        string="Rejected Qty",
        default=0.0
    )

    accept_qty = fields.Float(
        string="Accepted Qty",
        compute="_compute_accept_qty",
        store=True
    )

    @api.depends('product_uom_qty', 'reject_qty')
    def _compute_accept_qty(self):
        for move in self:
            move.accept_qty = max(
                move.product_uom_qty - move.reject_qty,
                0.0
            )

    @api.onchange('reject_qty')
    def _onchange_reject_qty(self):
        for move in self:
            if move.reject_qty > move.product_uom_qty:
                raise ValidationError(
                    "Rejected quantity cannot be greater than demand quantity."
                )
