from odoo import models, _


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def action_create_purchase_requisition(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "nakshatra.purchase.requisition",
            "views": [
                [
                    self.env.ref(
                        "nakshatra_purchase_requisition.view_purchase_requisition_form"
                    ).id,
                    "form",
                ]
            ],
            "name": _("Add Purchase Requisition"),
            "target": "new",
            "context": {
                "default_project_id": self.project_id.id if self.project_id else False,
            },
        }
