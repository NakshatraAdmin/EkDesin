# -*- coding: utf-8 -*-

from odoo import models, fields, api

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_mrp_products')
    product_id = fields.Many2one(
        'product.product', 'Product',
        domain="[('type', '=', 'consu'), ('id', 'in', allowed_product_ids)]",
        compute='_compute_product_id', store=True, copy=True, precompute=True,
        readonly=False, required=True, check_company=True)

    @api.depends('company_id')
    def _compute_allowed_mrp_products(self):
        for order in self:
            approved_boms = self.env['mrp.bom'].search([('state', '=', 'approved')])
            variants = approved_boms.mapped('product_tmpl_id.product_variant_ids')
            order.allowed_product_ids = variants