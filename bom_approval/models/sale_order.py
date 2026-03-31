from odoo import models, fields, _, api


class SaleOrder(models.Model):
    _inherit = "sale.order"

    allowed_template_ids = fields.Many2many('product.template', compute='_compute_allowed_products')
    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_products')

    @api.depends('company_id')
    def _compute_allowed_products(self):
        for order in self:
            approved_boms = self.env['mrp.bom'].search([('state', '=', 'approved')])
            templates = approved_boms.mapped('product_tmpl_id')
            variants = templates.mapped('product_variant_ids')
            order.allowed_product_ids = variants
            order.allowed_template_ids = templates