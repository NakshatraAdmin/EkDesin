from odoo import fields, models


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    purchase_requisition_count = fields.Integer(
        string="Purchase Requisitions", compute="_compute_purchase_requisition_count"
    )

    def _compute_purchase_requisition_count(self):
        for workorder in self:
            workorder.purchase_requisition_count = self.env[
                "nakshatra.purchase.requisition"
            ].search_count([("workorder_id", "=", workorder.id)])

    def action_view_purchase_requisitions(self):
        self.ensure_one()
        if not self.production_id or not self.production_id.project_id:
            return {"type": "ir.actions.act_window_close"}

        action = self.production_id.action_view_purchase_requisitions()

        if isinstance(action, dict):
            context = action.get("context", {})
            if isinstance(context, str):
                from ast import literal_eval

                context = literal_eval(context)

            context.update(
                {
                    "default_workorder_id": self.id,
                }
            )
            action["context"] = context
            action["domain"] = [("workorder_id", "=", self.id)]

        return action

    def action_create_purchase_requisition(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Create Purchase Requisition",
            "res_model": "nakshatra.purchase.requisition",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_project_id": self.production_id.project_id.id,
                "default_workorder_id": self.id,
                "default_reference": f"{self.production_id.name or ''}-{self.name or ''}",
            },
        }
