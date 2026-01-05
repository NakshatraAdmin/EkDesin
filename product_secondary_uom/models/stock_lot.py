from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockLot(models.Model):
    _inherit = "stock.lot"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals and vals['name']:
                existing_lot = self.search([('name', '=', vals['name'])], limit=1)
                if existing_lot:
                    raise ValidationError(
                        _('Lot/Serial Number must be unique! A lot with name "%s" already exists.')
                        % vals['name']
                    )

        return super(StockLot, self).create(vals_list)