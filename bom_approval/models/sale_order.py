from odoo import models, fields, _, api
from odoo.api import depends
from odoo.exceptions import ValidationError
from collections import Counter


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_allowed_boms = fields.Boolean(compute="allowed_bom_product", store=True)

    @api.depends('bom_ids', 'bom_ids.state', 'type')
    def allowed_bom_product(self):
        for product in self:
            has_approved_bom = any(bom.state == 'approved' for bom in product.bom_ids)
            product.is_allowed_boms = has_approved_bom or (
                not product.bom_ids and product.type == 'service'
            )



class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _check_unique_default_code(self, default_codes, excluded_ids=None):
        default_codes = [code for code in default_codes if code]
        if not default_codes:
            return

        duplicate_codes = [code for code, count in Counter(default_codes).items() if count > 1]
        if duplicate_codes:
            raise ValidationError(_("Internal Reference must be unique!"))

        domain = [('default_code', 'in', list(set(default_codes)))]
        if excluded_ids:
            domain.append(('id', 'not in', excluded_ids))

        if self.search_count(domain):
            raise ValidationError(_("Internal Reference must be unique!"))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_unique_default_code([vals.get('default_code') for vals in vals_list])
        return super().create(vals_list)

    def write(self, vals):
        default_code = vals.get('default_code')
        if default_code:
            self._check_unique_default_code([default_code], excluded_ids=self.ids)
        return super().write(vals)
