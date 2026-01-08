# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    show_dimensions = fields.Boolean(
        string="Show Dimensions",
        related="product_id.show_dimensions",
        store=True,
        readonly=True
    )

    length = fields.Float(string="Length")
    width = fields.Float(string="Width")
    height = fields.Float(string="Height")
    sec_uom_id_dimen = fields.Many2one(
        "uom.uom",
        string="Secondary UoM",
        readonly=True, store=True
    )
    sec_uom = fields.Char(
        string="UoM", 
        readonly=True, default="ft²")

    

    # cubic_feet = fields.Float(
    #     string="Cubic Feet",
    #     compute="_compute_cubic_feet",
    #     store=True,
    #     digits=(16, 3)
    # )

    def _prepare_stock_moves(self, picking):
        res = super()._prepare_stock_moves(picking)


        for move_vals in res:
            move_vals.update({
                'length': self.length,
                'width': self.width,
                'height': self.height,
                # 'secondary_product_uom_qty':self.secondary_product_uom_qty,
                'sec_uom': self.sec_uom,
                'assume_length': 0.0,
                'assume_width': 0.0,
                'assume_height': 0.0,
            })

        return res

    @api.depends("product_qty", "product_id.sec_uom_ratio",'length', 'width', 'height')
    def _compute_secondary_product_uom_qty(self):
        sqft_uom = self.env['uom.uom'].search([('name', '=', 'ft²')], limit=1)
        for line in self:
            if line.product_id.is_need_secondary_uom and line.product_qty > 0:
                line.secondary_product_uom_qty = (
                    line.product_id.sec_uom_ratio * line.product_qty
                )
            else:
                line.secondary_product_uom_qty = 0
            if line.length and line.width and line.height:
                line.secondary_product_uom_qty = (line.length * line.width * line.height)*line.product_qty 
            else:
                line.secondary_product_uom_qty = 0.0

