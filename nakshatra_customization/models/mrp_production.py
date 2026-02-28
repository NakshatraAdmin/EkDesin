from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    purchase_requisition_count = fields.Integer(
        string="Purchase Requisitions", compute="_compute_purchase_requisition_count"
    )

    def _compute_purchase_requisition_count(self):
        for manufacture_order in self:
            manufacture_order.purchase_requisition_count = self.env[
                "nakshatra.purchase.requisition"
            ].search_count([("mrp_ids", "=", manufacture_order.id)])

    def action_view_purchase_requisitions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Purchase Requisitions",
            "res_model": "nakshatra.purchase.requisition",
            "view_mode": "list,form",
            "domain": [("mrp_ids", "=", self.id)],
            "context": {"default_mrp_ids": self.id},
            "target": "current",
        }
