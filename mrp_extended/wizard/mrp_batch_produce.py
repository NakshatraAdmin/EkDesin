# -*- coding: utf-8 -*-

from odoo import api, models


class MrpBatchProduce(models.TransientModel):
    _inherit = 'mrp.batch.produce'

    @api.depends('production_id')
    def _compute_lot_name(self):
        stock_lot = self.env['stock.lot']
        for wizard in self:
            if wizard.lot_name:
                continue

            production = wizard.production_id
            lot_name = production.lot_producing_id.name
            if not lot_name and production.product_id.tracking in ('lot', 'serial'):
                lot_name = stock_lot._generate_lot_serial_number(production.product_id)

            wizard.lot_name = lot_name
