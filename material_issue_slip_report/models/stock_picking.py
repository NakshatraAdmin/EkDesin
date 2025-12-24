from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    material_requested_by_id = fields.Many2one(
        'res.users',
        string="Requisition By"
        )

    material_received_by_id = fields.Many2one(
        'res.users',
        string="Material Received By:"
    )

    
class StockMove(models.Model):
    _inherit = 'stock.move'

    remark = fields.Text(string="Remark")
    material_issued_by_id = fields.Many2one(
        'res.users',
        string="Material Issued By:"
    )
