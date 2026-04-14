from odoo import models, fields, _, api


class SaleOrder(models.Model):
    _inherit = "sale.order"

    allowed_template_ids = fields.Many2many('product.template', compute='_compute_allowed_products')
    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_products')

    @api.depends('company_id')
    def _compute_allowed_products(self):
        for order in self:
            all_templates = self.env['product.template'].search([])
            approved_boms = self.env['mrp.bom'].search([('state', '=', 'approved')])
            approved_templates = approved_boms.mapped('product_tmpl_id')

            all_bom_templates = self.env['mrp.bom'].search([]).mapped('product_tmpl_id')
            no_bom_templates = all_templates - all_bom_templates
            final_templates = approved_templates | no_bom_templates
            final_variants = final_templates.mapped('product_variant_ids')
            for order in self:
                order.allowed_template_ids = final_templates
                order.allowed_product_ids = final_variants