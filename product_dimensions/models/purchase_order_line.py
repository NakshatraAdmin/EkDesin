# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    show_dimensions = fields.Boolean(
        string="Show Dimensions",
        related="product_id.show_dimensions",
        readonly=True,
        store=True
    )
    width = fields.Float(
        string="Width",
        related="product_id.width",
        store=True,
        readonly=True,
    )
    length = fields.Float(
        string="Length",
        related="product_id.length",
        store=True,
        readonly=True,
    )
    height = fields.Float(
        string="Height",
        related="product_id.height",
        store=True,
        readonly=True,
    )

    @api.onchange('product_id', 'product_qty')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id
            # Copy dimensions from product when product is selected
            if self.product_id.show_dimensions:
                self.width = self.product_id.width
                self.length = self.product_id.length
                self.height = self.product_id.height
