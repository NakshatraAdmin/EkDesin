# -*- coding: utf-8 -*-
from odoo import models, fields,api
from odoo.exceptions import UserError



class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    show_dimensions = fields.Boolean(
        related="product_id.show_dimensions",
        readonly=True,
        store=True,
    )

    width = fields.Float(
        readonly=False,
        store=True,
    )
    length = fields.Float(
        readonly=False,
        store=True,
    )
    height = fields.Float(
        readonly=False,
        store=True,
    )
    sec_uom = fields.Char(
        string="UoM", 
        readonly=True, default="ft²")
    
    secondary_product_uom_qty = fields.Float(
        string="Secondary Quantity",
        help="Secondary UoM Quantity",
        compute="_compute_secondary_product_uom_qty",
        store=True,
    )

    @api.depends("product_qty", "product_id.sec_uom_ratio",'length', 'width', 'height')
    def _compute_secondary_product_uom_qty(self):
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

