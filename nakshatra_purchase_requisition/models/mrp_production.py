from odoo import models, fields, _


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    pr_id = fields.Many2many(
        "nakshatra.purchase.requisition", string="Purchase Requisition"
    )

    def action_create_purchase_requisition(self):
        self.ensure_one()
        # Step 1: Create the PR first
        pr = (
            self.env["nakshatra.purchase.requisition"]
            .with_context(default_values={"mrp_ids": True})
            .create(
                {
                    "project_id": self.project_id.id,
                    "mrp_ids": [(6, 0, [self.id])],
                }
            )
        )

        # Step 2: Redirect to the created PR form
        return {
            "type": "ir.actions.act_window",
            "res_model": "nakshatra.purchase.requisition",
            "view_mode": "form",
            "res_id": pr.id,
            "target": "current",
        }

    def action_create_pr(self):
        self.ensure_one()
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
            "target": "current",
            "context": {
                "default_project_id": self.project_id.id if self.project_id else False,
                "default_mrp_ids": [(6, 0, [self.id])],
                "default_values": {"mrp_ids": True},
            },
        }
