# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

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
    secondary_unit_price = fields.Float(
        string="Secondary Unit Price",
        help="Secondary Unit Price",
        store=True,
    )

    @api.depends('product_qty', 'price_unit', 'taxes_id', 'discount', 'secondary_unit_price', 'secondary_product_uom_qty')
    def _compute_amount(self):
        """Override the amount computation to use secondary fields when available"""
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            totals = next(iter(tax_results['totals'].values()))
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })

    def _convert_to_tax_base_line_dict(self):
        """Override to use secondary fields when both are available"""
        self.ensure_one()

        # Check if both secondary fields have values
        if self.secondary_unit_price and self.secondary_product_uom_qty:
            price_unit = self.secondary_unit_price
            quantity = self.secondary_product_uom_qty
        else:
            price_unit = self.price_unit
            quantity = self.product_qty

        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.order_id.partner_id,
            currency=self.order_id.currency_id,
            product=self.product_id,
            taxes=self.taxes_id,
            price_unit=price_unit,
            quantity=quantity,
            discount=self.discount,
            price_subtotal=self.price_subtotal,
        )

    @api.onchange('secondary_unit_price', 'secondary_product_uom_qty')
    def _onchange_secondary_fields(self):
        """Trigger amount recalculation when secondary fields change"""
        self._compute_amount()

    def _prepare_account_move_line(self, move=False):
        """Override to use secondary fields in account move line preparation if needed"""
        res = super(PurchaseOrderLine, self)._prepare_account_move_line(move)

        # If secondary fields are used, update the account move line accordingly
        if self.secondary_unit_price and self.secondary_product_uom_qty:
            res.update({
                'quantity': self.secondary_product_uom_qty,
                'price_unit': self.secondary_unit_price,
            })

        return res

    @api.onchange('product_id', 'product_qty')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id
            if self.product_id.is_need_secondary_uom:
                self.sec_uom_id = self.product_id.sec_uom_id
                if self.product_qty > 0:
                    self.secondary_product_uom_qty = (
                        self.product_id.sec_uom_ratio * self.product_qty
                    )
                else:
                    self.secondary_product_uom_qty = 0

    @api.depends("product_qty", "product_id.sec_uom_ratio")
    def _compute_secondary_product_uom_qty(self):
        for line in self:
            if line.product_id.is_need_secondary_uom and line.product_qty > 0:
                line.secondary_product_uom_qty = (
                    line.product_id.sec_uom_ratio * line.product_qty
                )
            else:
                line.secondary_product_uom_qty = 0

    @api.onchange('secondary_product_uom_qty')
    def _onchange_secondary_product_uom_qty(self):
        if self.product_id.is_need_secondary_uom and self.secondary_product_uom_qty > 0:
            if self.product_id.sec_uom_ratio:
                self.product_qty = (
                    self.secondary_product_uom_qty / self.product_id.sec_uom_ratio
                )
        else:
            self.product_qty = 0

    def _inverse_secondary_product_uom_qty(self):
        for line in self:
            if line.product_id.is_need_secondary_uom and line.secondary_product_uom_qty > 0:
                if line.product_id.sec_uom_ratio:
                    line.product_qty = line.secondary_product_uom_qty / line.product_id.sec_uom_ratio
            else:
                line.product_qty = 0