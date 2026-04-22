# -*- coding: utf-8 -*-

from odoo import api, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.model
    def _get_auto_lot_product_from_vals(self, vals):
        if vals.get('lot_id'):
            return self.env['product.product']

        move = self.env['stock.move']
        if vals.get('move_id'):
            move = self.env['stock.move'].browse(vals['move_id'])

        product_id = vals.get('product_id') or (move.product_id.id if move.exists() else False)
        if not product_id:
            return self.env['product.product']

        product = self.env['product.product'].browse(product_id)
        if not (
            move.exists() and move.picking_id and
            move.picking_id.picking_type_id.code == 'incoming' and
            product.exists() and product.tracking in ('lot', 'serial')
        ):
            return self.env['product.product']

        category_type = self.env['stock.lot']._get_category_type_from_product(product)
        return product if category_type == 'rm' else self.env['product.product']

    @api.model
    def _should_regenerate_lot_name(self, lot_name, reserved_names):
        if not lot_name:
            return True

        StockLot = self.env['stock.lot']
        if not StockLot._is_auto_lot_serial_name(lot_name):
            return False
        if lot_name in reserved_names:
            return True
        return StockLot._lot_serial_number_exists(lot_name)

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        reserved_names = set()
        for vals in vals_list:
            try:
                product = self._get_auto_lot_product_from_vals(vals)
                if not product:
                    continue

                lot_name = vals.get('lot_name')
                if self._should_regenerate_lot_name(lot_name, reserved_names):
                    lot_name = self.env['stock.lot']._generate_lot_serial_number(
                        product,
                        reserved_names=reserved_names,
                    )
                    vals['lot_name'] = lot_name

                reserved_names.add(lot_name)
            except Exception:
                pass

        return super(StockMoveLine, self).create(vals_list)
