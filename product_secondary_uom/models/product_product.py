# -*- coding: utf-8 -*-


from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_need_secondary_uom = fields.Boolean(
        string="Need Secondary UoM's",
        help="Enable this field for using the secondary UoM",
        related="product_tmpl_id.is_need_secondary_uom",
        store=True,
    )
    sec_uom_id = fields.Many2one(
        "uom.uom",
        string="Secondary UoM",
        help="Select the Secondary UoM",
        related="product_tmpl_id.sec_uom_id",
        store=True,
    )
    sec_uom_ratio = fields.Float(
        string="Secondary UoM Ratio",
        help="Choose the ratio with the base Unit of Measure.",
        related="product_tmpl_id.sec_uom_ratio",
        store=True,
    )
    ratio = fields.Char(
        string="Ratio",
        help="Ratio of base UoM and the secondary UoM",
        compute="_compute_secondary_uom_ratio",
    )
    inverse_ratio = fields.Char(
        string="Inverse Ratio",
        help="Shows the reverse ratio from the Secondary UoM to the base UoM",
        compute="_compute_secondary_uom_ratio",
    )
    sec_uom_qty = fields.Float(compute="_compute_total_qty", string="Secondary UoM Qty")
    std_unit_cost = fields.Float(
        string="STD Unit Cost",
        compute="_compute_std_unit_cost",
        store=True,
    )
    consumable_unit_rate = fields.Float(
        string="Consumable Unit Rate",
        compute="_compute_consumable_unit_rate",
        store=True,
    )
    landing_cost = fields.Float(string="Landing Cost")
    net_unit_cost = fields.Float(
        string="Net Unit Cost",
        compute="_compute_net_unit_cost",
        store=True,
    )

    is_need_consumption_uom = fields.Boolean(
        string="Need Consumption UoM's",
        help="Enable this field for using the Consumption UoM",
        store=True,
    )
    consumption_product_uom_qty = fields.Float(compute="_compute_consumption_total_qty", string="Consumption UoM Qty")
    consumption_uom_ratio = fields.Float(
        string="Consumption UoM Ratio",
        help="Choose the ratio with the base Unit of Measure.",
        store=True,
    )
    consumption_uom_id = fields.Many2one(
        "uom.uom",
        string="Consumption UoM",
        help="Select the Consumption UoM",
        store=True,
    )
    consumption_ratio = fields.Char(
        string="Consumption Ratio",
        help="Ratio of base UoM and the Consumption UoM",
        compute="_compute_consumption_uom_ratio"
    )
    consumption_inverse_ratio = fields.Char(
        string="Consumption Inverse Ratio",
        help="Shows the reverse ratio from the Consumption UoM to the base UoM",
        compute="_compute_consumption_uom_ratio"
    )

    @api.depends("alternet_unit_qty", "standard_price")
    def _compute_std_unit_cost(self):
        for product_tmpl in self:
            product_tmpl.std_unit_cost = product_tmpl.alternet_unit_qty * product_tmpl.standard_price

    @api.depends("net_unit_cost", "sec_uom_ratio")
    def _compute_consumable_unit_rate(self):
        for product_tmpl in self:
            if product_tmpl.sec_uom_ratio > 0:
                product_tmpl.consumable_unit_rate = product_tmpl.net_unit_cost / product_tmpl.sec_uom_ratio
            else:
                product_tmpl.consumable_unit_rate = 0.0

    @api.depends("std_unit_cost", "landing_cost")
    def _compute_net_unit_cost(self):
        for product_tmpl in self:
            landing_multiplier = (product_tmpl.landing_cost / 100) if product_tmpl.landing_cost else 0
            product_tmpl.net_unit_cost = product_tmpl.std_unit_cost * (1 + landing_multiplier)

    @api.depends("sec_uom_qty", "qty_available")
    def _compute_total_qty(self):
        for product in self:
            if not product.sec_uom_ratio or not product.qty_available:
                print("self===",self[25].name,product.sec_uom_ratio,product.qty_available)
                product.sec_uom_qty = 0
                continue
            product.sec_uom_qty = product.qty_available * product.sec_uom_ratio

    @api.depends("consumption_product_uom_qty", "qty_available")
    def _compute_consumption_total_qty(self):
        for product in self:
            if not product.consumption_uom_ratio or not product.qty_available:
                product.consumption_product_uom_qty = 0
                continue
            product.consumption_product_uom_qty = product.qty_available * product.consumption_uom_ratio

    @api.depends("sec_uom_id", "sec_uom_ratio")
    def _compute_secondary_uom_ratio(self):
        for product in self:
            if not product.sec_uom_id or product.sec_uom_ratio == 0:
                product.ratio = False
                product.inverse_ratio = False
                continue
            
            product.ratio = (
                f"1 {product.uom_id.name} = "
                f"{product.sec_uom_ratio} {product.sec_uom_id.name}"
            )
            inverse_value = 1 / product.sec_uom_ratio if product.sec_uom_ratio else 0
            product.inverse_ratio = (
                f"1 {product.sec_uom_id.name} = "
                f"{inverse_value:.2f} {product.uom_id.name}"
            )

    @api.depends("consumption_uom_id", "consumption_uom_ratio")
    def _compute_consumption_uom_ratio(self):
        for product_tmpl in self:
            if not product_tmpl.consumption_uom_id or product_tmpl.consumption_uom_ratio == 0:
                product_tmpl.consumption_ratio = False
                product_tmpl.consumption_inverse_ratio = False
                continue

            product_tmpl.consumption_ratio = (
                f"1 {product_tmpl.uom_id.name} = "
                f"{product_tmpl.consumption_uom_ratio} "
                f"{product_tmpl.consumption_uom_id.name}"
            )
            inverse_value = 1 / product_tmpl.consumption_uom_ratio if product_tmpl.consumption_uom_ratio else 0
            product_tmpl.consumption_inverse_ratio = (
                f"1 {product_tmpl.consumption_uom_id.name} = "
                f"{inverse_value:.2f} {product_tmpl.uom_id.name}"
            )