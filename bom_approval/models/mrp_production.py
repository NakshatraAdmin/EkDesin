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
        all_templates = self.env['product.template'].search([])
        approved_boms = self.env['mrp.bom'].search([('state', '=', 'approved')])
        approved_templates = approved_boms.mapped('product_tmpl_id')
        all_bom_templates = self.env['mrp.bom'].search([]).mapped('product_tmpl_id')
        no_bom_templates = all_templates - all_bom_templates
        final_templates = approved_templates | no_bom_templates
        final_variants = final_templates.mapped('product_variant_ids')
        for record in self:
            record.allowed_product_ids = final_variants
