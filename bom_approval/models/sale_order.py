from odoo import models, fields, _, api
from odoo.api import depends


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_allowed_bom = fields.Boolean(compute="allowed_bom_product", store=True)

    @api.depends('bom_ids', 'bom_ids.state')
    def allowed_bom_product(self):
        is_allowed_bom = False
        for product in self:
            if not product.bom_ids:
                is_allowed_bom = True
            if all (bom.state == 'approved' for bom in product.bom_ids):
                is_allowed_bom = True
            product.is_allowed_bom = is_allowed_bom

