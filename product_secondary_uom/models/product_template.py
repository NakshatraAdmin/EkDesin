# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api


class ItemType(models.Model):
    _name = 'item.type'
    _description = 'Item Type'

    name = fields.Char(string='Item Type Name', required=True)


class ProductGroup(models.Model):
    _name = 'product.group'
    _description = 'Product Group'

    name = fields.Char(string='Product Group Name', required=True)


class SubProductGroup(models.Model):
    _name = 'sub.product.group'
    _description = 'Sub Product Group'

    name = fields.Char(string='Sub Product Group Name', required=True)


class CostSegment(models.Model):
    _name = 'cost.segment'
    _description = 'Cost Segment'

    name = fields.Char(string='Cost Segment Name', required=True)
    

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    item_type_id = fields.Many2one('item.type', string='Item Type')
    product_group_id = fields.Many2one('product.group', string='Product Group')
    sub_product_group_id = fields.Many2one('sub.product.group', string='Sub Product Group')
    cost_segment_id = fields.Many2one('cost.segment', string='Cost Segment')
    std_unit_cost = fields.Float(
        string="STD Unit Cost",
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
    taxes_id = fields.Many2many(
        'account.tax', 
        'product_taxes_rel', 
        'prod_id', 
        'tax_id',
        string='Customer Taxes',
        domain=[('type_tax_use', '=', 'sale')],
    )
    is_need_secondary_uom = fields.Boolean(
        string="Need Secondary UoM's",
        help="Enable this field for using the secondary UoM",
    )
    sec_uom_id = fields.Many2one(
        "uom.uom",
        string="Secondary UoM",
        help="Select the Secondary UoM",
    )
    sec_uom_ratio = fields.Float(
        string="Alternate Std Qty",
        help="Choose the ratio with the base Unit of Measure.",
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
    is_need_consumption_uom = fields.Boolean(
        string="Need Consumption UoM's",
        help="Enable this field for using the Consumption UoM",
        store=True,
    )
    consumption_uom_id = fields.Many2one(
        "uom.uom",
        string="Consumption UoM",
        help="Select the Secondary UoM",
    )
    consumption_uom_ratio = fields.Float(
        string="Consumption Alternate Std Qty",
        help="Choose the ratio with the base Unit of Measure.",
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
    weight = fields.Float(string="Weight")
    height = fields.Float(string="Height")
    length = fields.Float(string="Length")
    width = fields.Float(string="Width")
    depth = fields.Float(string="Depth")
    alternet_unit_qty = fields.Float(
        string="Purchase Unit Qty",
        help="Enter the alternate unit quantity for conversion."
    )
    alternet_ratio = fields.Char(
        string="Alternate Ratio",
        compute="_compute_alternet_conversion_ratios",
        store=True,
        help="Conversion ratio between base UoM and alternate UoM."
    )
    inverse_alternet_ratio = fields.Char(
        string="Inverse Alternate Ratio",
        compute="_compute_alternet_conversion_ratios",
        store=True,
        help="Reverse conversion ratio from alternate UoM to base UoM."
    )
    uom_po_name = fields.Char(string='Purchase Unit of Measure Name', related='uom_po_id.name', readonly=True)

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        if 'std_unit_cost' in vals:
            self._update_variant_costs()
        return res

    def _update_variant_costs(self):
        for template in self:
            if template.product_variant_ids:
                template.product_variant_ids.write({
                    'standard_price': template.std_unit_cost
                })

    @api.depends('uom_id', 'uom_po_id', 'alternet_unit_qty')
    def _compute_alternet_conversion_ratios(self):
        for product_tmpl in self:
            if not product_tmpl.uom_id or not product_tmpl.uom_po_id or product_tmpl.alternet_unit_qty <= 0:
                product_tmpl.alternet_ratio = False
                product_tmpl.inverse_alternet_ratio = False
                continue

            product_tmpl.alternet_ratio = (
                f"1 {product_tmpl.uom_id.name} = "
                f"{product_tmpl.alternet_unit_qty:.2f} {product_tmpl.uom_po_id.name}"
            )
            inverse_value = 1 / product_tmpl.alternet_unit_qty if product_tmpl.alternet_unit_qty else 0
            product_tmpl.inverse_alternet_ratio = (
                f"1 {product_tmpl.uom_po_id.name} = "
                f"{inverse_value:.2f} {product_tmpl.uom_id.name}"
            )

    @api.depends("std_unit_cost", "landing_cost")
    def _compute_net_unit_cost(self):
        for product_tmpl in self:
            landing_multiplier = (product_tmpl.landing_cost / 100) if product_tmpl.landing_cost else 0
            product_tmpl.net_unit_cost = product_tmpl.std_unit_cost * (1 + landing_multiplier)

    @api.depends("net_unit_cost", "sec_uom_ratio")
    def _compute_consumable_unit_rate(self):
        for product_tmpl in self:
            if product_tmpl.sec_uom_ratio > 0:
                product_tmpl.consumable_unit_rate = product_tmpl.net_unit_cost / product_tmpl.sec_uom_ratio
            else:
                product_tmpl.consumable_unit_rate = 0.0

    @api.onchange("alternet_unit_qty", "standard_price")
    def _onchange_std_unit_cost(self):
        for product_tmpl in self:
            product_tmpl.std_unit_cost = product_tmpl.alternet_unit_qty * product_tmpl.standard_price

    @api.depends("sec_uom_id", "sec_uom_ratio")
    def _compute_secondary_uom_ratio(self):
        for product_tmpl in self:
            if not product_tmpl.sec_uom_id or product_tmpl.sec_uom_ratio == 0:
                product_tmpl.ratio = False
                product_tmpl.inverse_ratio = False
                continue

            product_tmpl.ratio = (
                f"1 {product_tmpl.uom_id.name} = "
                f"{product_tmpl.sec_uom_ratio} "
                f"{product_tmpl.sec_uom_id.name}"
            )
            inverse_value = 1 / product_tmpl.sec_uom_ratio if product_tmpl.sec_uom_ratio else 0
            product_tmpl.inverse_ratio = (
                f"1 {product_tmpl.sec_uom_id.name} = "
                f"{inverse_value:.2f} {product_tmpl.uom_id.name}"
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

    @api.model
    def get_product_warehouse_details(self, product_id, warehouse_id=None):
        try:
            product_product = self.env['product.product'].browse(product_id)
            if not product_product.exists():
                return {"error": "Product not found"}

            # Get all warehouses
            warehouses = self.env['stock.warehouse'].search([])
            warehouse_details = []

            for warehouse in warehouses:
                product_with_context = product_product.with_context(warehouse=warehouse.id)
                qty_available = product_with_context.qty_available
                virtual_available = product_with_context.virtual_available

                warehouse_details.append(
                    f"{warehouse.name}: {qty_available}, Forecasted: {virtual_available}"
                )

            # ✅ Get actual stock entries directly from quant table
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product_product.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
                ('location_id.company_id', '=', self.env.company.id),
            ])

            # ✅ Build the final location list from quants (same as smart button)
            location_qty_map = defaultdict(float)
            for quant in quants:
                location_qty_map[quant.location_id.complete_name] += quant.quantity

            location_details = [
                f"{location_name}: {qty}"
                for location_name, qty in location_qty_map.items()
            ]

            return {
                'warehouse_details': warehouse_details,
                'location_details': location_details,
            }

        except Exception as e:
            return {'error': str(e)}


