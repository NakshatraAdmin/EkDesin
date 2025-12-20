from odoo import models, fields

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
