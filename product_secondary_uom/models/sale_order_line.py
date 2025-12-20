# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sec_uom_id = fields.Many2one(
        "uom.uom",
        string="Secondary UoM",
        related="product_id.sec_uom_id",
        readonly=True,
    )
    secondary_product_uom_qty = fields.Float(
        string="Secondary Quantity",
        help="Secondary UoM Quantity",
        compute="_compute_secondary_product_uom_qty",
        inverse="_inverse_secondary_product_uom_qty",
        store=True,
    )
    is_need_secondary_uom = fields.Boolean(
        related="product_id.is_need_secondary_uom",
        store=True,
        readonly=True,
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id
            self.is_need_secondary_uom = self.product_id.is_need_secondary_uom  # Set the secondary UoM need
            if self.product_id.is_need_secondary_uom:
                self.sec_uom_id = self.product_id.sec_uom_id
                self.product_uom_qty = self.product_uom_qty or 1
                if self.product_uom_qty > 0:
                    self.secondary_product_uom_qty = (
                        self.product_id.sec_uom_ratio * self.product_uom_qty
                    )
                else:
                    self.secondary_product_uom_qty = 0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id
            if self.product_id.is_need_secondary_uom:
                self.sec_uom_id = self.product_id.sec_uom_id
                self.product_uom_qty = self.product_uom_qty or 1
                if self.product_uom_qty > 0:
                    self.secondary_product_uom_qty = (
                        self.product_id.sec_uom_ratio * self.product_uom_qty
                    )
                else:
                    self.secondary_product_uom_qty = 0

    @api.depends("product_uom_qty", "product_id.sec_uom_ratio")
    def _compute_secondary_product_uom_qty(self):
        for line in self:
            if line.product_id.is_need_secondary_uom and line.product_uom_qty > 0:
                line.secondary_product_uom_qty = (
                    line.product_id.sec_uom_ratio * line.product_uom_qty
                )
            else:
                line.secondary_product_uom_qty = 0

    @api.onchange('secondary_product_uom_qty')
    def _onchange_secondary_product_uom_qty(self):
        if self.product_id.is_need_secondary_uom and self.secondary_product_uom_qty > 0:
            if self.product_id.sec_uom_ratio:
                self.product_uom_qty = (
                    self.secondary_product_uom_qty / self.product_id.sec_uom_ratio
                )
        else:
            self.product_uom_qty = 0

    def _inverse_secondary_product_uom_qty(self):
        for line in self:
            if line.product_id.is_need_secondary_uom and line.secondary_product_uom_qty > 0:
                if line.product_id.sec_uom_ratio:
                    line.product_uom_qty = (
                        line.secondary_product_uom_qty / line.product_id.sec_uom_ratio
                    )
            else:
                line.product_uom_qty = 0
