from odoo import models, fields, _
from odoo.exceptions import ValidationError, UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    pr_id = fields.Many2one(
        "nakshatra.purchase.requisition", string="Related PR", readonly=True
    )
    state = fields.Selection(
        selection_add=[("sales_order", "Sales Order"), ("sale", "Confirmed")]
    )

    def _confirmation_error_message(self):
        """Return whether order can be confirmed or not if not then returm error message."""
        self.ensure_one()
        if self.state not in {"approved", "draft", "sent", "sales_order"}:
            return _("Some orders are not in a state requiring confirmation.")
        if any(
            not line.display_type and not line.is_downpayment and not line.product_id
            for line in self.order_line
        ):
            return _("A line on these orders missing a product, you cannot confirm it.")

        return False

    def action_state_convert_to_so(self):
        is_approved = self.is_approved
        if not is_approved:
            raise UserError(
                _("This order requires approval before converting to Sales Order.")
            )
        self.state = "sales_order"

    def action_confirm(self):
        res = super().action_confirm()
        self.action_create_purchase_requisition()
        return res

    def action_create_purchase_requisition(self):
        self.ensure_one()

        if not self.project_id:
            raise UserError(_("Please select Project first."))

        direct_pr_lines = []

        # Prepare direct lines for products without BoM (only consumables)
        for line in self.order_line.filtered(
            lambda line: line.product_id.type == "consu"
        ):
            product = line.product_id
            qty = line.product_uom_qty
            bom = (
                self.env["mrp.bom"]
                ._bom_find(products=product, company_id=self.company_id.id)
                .get(product)
            )

            if not bom or not bom.exists():
                direct_pr_lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "required_qty": qty,
                            "requested_qty": qty,
                            "approved_qty": 0.0,
                            "uom_id": product.uom_id.id,
                            "item_status": "draft",
                            "project_id": self.project_id.id,
                            "is_direct_line": True,
                        },
                    )
                )

        # Find MOs related to this SO's project
        mo_domain = [("project_id", "=", self.project_id.id)]
        related_mos = self.env["mrp.production"].search(mo_domain)

        if not related_mos and not direct_pr_lines:
            pass
            # raise ValidationError(_("No MOs or direct products found for PR creation."))

        # Create the Purchase Requisition
        pr = self.env["nakshatra.purchase.requisition"].create(
            {
                "project_id": self.project_id.id,
                "line_ids": direct_pr_lines,
                "reference": self.name,
                "sale_order_id": self.id,
            }
        )

        # Set MRP IDs after creation to trigger the proper updates
        pr.write({"mrp_ids": [(6, 0, related_mos.ids)]})
        pr.create_rfq_from_pr()
        pr.write({"state": "approved"})


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    pr_id = fields.Many2one(
        "nakshatra.purchase.requisition",
        string="Purchase Requisition",
        help="Link to the related Purchase Requisition",
    )

    def write(self, vals):
        for line in self:
            if (
                "product_uom_qty" in vals
                and line.order_id.state == "sale"
                and line.product_uom_qty != vals.get("product_uom_qty")
            ):
                raise ValidationError(
                    _("You cannot modify the quantity in a confirmed Sale Order.")
                )
        return super().write(vals)
