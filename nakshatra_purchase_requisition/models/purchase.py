from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    pr_id = fields.Many2one("nakshatra.purchase.requisition", string="PR")


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    pr_id = fields.Many2one("nakshatra.purchase.requisition", string="PR")
