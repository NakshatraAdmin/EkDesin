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


    @api.depends('product_qty', 'price_unit', 'taxes_id', 'discount')
    def _compute_amount(self):
        for line in self:
            base_line = line._prepare_base_line_for_taxes_computation()
            self.env['account.tax']._add_tax_details_in_base_line(base_line, line.company_id)
            line.price_subtotal = base_line['tax_details']['raw_total_excluded_currency']
            line.price_total = base_line['tax_details']['raw_total_included_currency']
            line.price_tax = line.price_total - line.price_subtotal

    def _prepare_base_line_for_taxes_computation(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        if self.secondary_unit_price and self.secondary_product_uom_qty:
            price_unit = self.secondary_unit_price
            quantity = self.secondary_product_uom_qty
        else:
            price_unit = self.price_unit
            quantity = self.product_qty
        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            self,
            tax_ids=self.taxes_id,
            quantity=self.product_qty,
            partner_id=self.order_id.partner_id,
            currency_id=self.order_id.currency_id or self.order_id.company_id.currency_id,
            rate=self.order_id.currency_rate,
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
        if self.product_id and self.product_id.is_need_secondary_uom and self.secondary_product_uom_qty > 0:
            if self.product_id.sec_uom_ratio:
                self.product_qty = (
                    self.secondary_product_uom_qty / self.product_id.sec_uom_ratio
                )

    def _inverse_secondary_product_uom_qty(self):
        for line in self:
            # Only update product_qty if product has secondary UOM enabled
            # Don't reset to 0 if product doesn't have secondary UOM - preserve existing value
            if line.product_id and line.product_id.is_need_secondary_uom and line.secondary_product_uom_qty > 0:
                if line.product_id.sec_uom_ratio:
                    line.product_qty = line.secondary_product_uom_qty / line.product_id.sec_uom_ratio