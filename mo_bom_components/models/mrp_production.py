from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    mo_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        compute="_compute_mo_details",
        store=True,
    )

    mo_product_tmpl_id = fields.Many2one(
        "product.product",
        string="MO Finished Product",
        store=True,
    )
    mo_product_id = fields.Many2one(
        "product.product",
        string="MO BOM Product Variant",
        compute="_compute_mo_details",
        store=True,
    )

    @api.depends(
        "move_ids_without_package.raw_material_production_id",
        "origin"
    )
    def _compute_mo_details(self):
        for picking in self:
            mo = False

            # Case 1: Picking created from MO (Pick Components)
            moves = picking.move_ids_without_package.filtered(
                lambda m: m.raw_material_production_id
            )
            if moves:
                mo = moves[0].raw_material_production_id

            # Case 2: Fallback using origin
            if not mo and picking.origin:
                mo = self.env["mrp.production"].search(
                    [("name", "=", picking.origin)],
                    limit=1,
                )

            picking.mo_id = mo
            picking.mo_product_id = mo.bom_id.product_id if mo.bom_id.product_id else False
            picking.mo_product_tmpl_id = mo.product_id if mo else False