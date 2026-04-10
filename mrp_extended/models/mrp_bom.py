from odoo import api, models, fields


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    note = fields.Html(string="Note")
    secondary_product_uom_qty = fields.Float(
        string="Secondary Quantity",
        help="Secondary UoM Quantity",
        compute="_compute_secondary_product_uom_qty",
        store=True,
        digits=(16, 3),
    )

    @api.depends("product_qty", "product_id.sec_uom_ratio", 'length', 'width', 'height')
    def _compute_secondary_product_uom_qty(self):
        super()._compute_secondary_product_uom_qty()
        for line in self:
            if line.length and line.width and line.height and line.product_qty:
                line.secondary_product_uom_qty = ((line.length * line.width * line.height * line.product_qty) / 12 / 12 / 12) * 1.5

    @api.onchange('product_id')
    def _onchange_bom_product_id(self):
        if self.product_id:
            self.note = self.product_id.description
