# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    @api.model
    def _get_lot_serial_prefix(self, product, date=None):
        category_type = self._get_category_type_from_product(product)
        fy_string = self._get_fy_string(date)
        category_identifier = self._get_category_identifier(category_type)
        return f'ED/{fy_string}/{category_identifier}'

    @api.model
    def _is_auto_lot_serial_name(self, name):
        pattern = r'^ED/FY\d{2}-\d{2}/(LOT-RM|LOT-SFG|SR-FG)\d{8}$'
        return bool(name and re.match(pattern, name))

    @api.model
    def _extract_lot_serial_sequence(self, name, prefix):
        pattern = rf'^{re.escape(prefix)}(\d{{8}})$'
        match = re.match(pattern, name or '')
        return int(match.group(1)) if match else 0

    @api.model
    def _get_max_lot_serial_sequence(self, prefix):
        max_seq = 0

        self.env.cr.execute("""
            SELECT name FROM stock_lot
            WHERE name LIKE %s
            ORDER BY name DESC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (f'{prefix}%',))

        result = self.env.cr.fetchone()
        if result and result[0]:
            max_seq = max(max_seq, self._extract_lot_serial_sequence(result[0], prefix))

        # Receipt move lines can reserve lot_name before stock.lot is created.
        self.env.cr.execute("""
            SELECT lot_name FROM stock_move_line
            WHERE lot_name LIKE %s
            ORDER BY lot_name DESC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (f'{prefix}%',))

        result = self.env.cr.fetchone()
        if result and result[0]:
            max_seq = max(max_seq, self._extract_lot_serial_sequence(result[0], prefix))

        return max_seq

    @api.model
    def _lot_serial_number_exists(self, lot_number):
        if not lot_number:
            return False
        if self.search([('name', '=', lot_number)], limit=1):
            return True
        return bool(self.env['stock.move.line'].search([('lot_name', '=', lot_number)], limit=1))

    @api.model
    def _generate_lot_serial_number(self, product, date=None, reserved_names=None):
        reserved_names = set(reserved_names or [])
        prefix = self._get_lot_serial_prefix(product, date)
        max_seq = self._get_max_lot_serial_sequence(prefix)
        for name in reserved_names:
            max_seq = max(max_seq, self._extract_lot_serial_sequence(name, prefix))

        next_seq = max_seq + 1
        while True:
            lot_number = f"{prefix}{str(next_seq).zfill(8)}"
            if lot_number not in reserved_names and not self._lot_serial_number_exists(lot_number):
                return lot_number
            next_seq += 1

    @api.model
    def _get_next_serial(self, company, product):
        if not product or product.tracking == 'none':
            return False
        return self._generate_lot_serial_number(product)

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        reserved_names = set()
        for vals in vals_list:
            if vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                if product.tracking in ('lot', 'serial'):
                    provided_name = vals.get('name', '').strip() if vals.get('name') else ''
                    if not provided_name or not self._is_auto_lot_serial_name(provided_name):
                        create_date = (
                            vals.get('create_date') or
                            self.env.context.get('default_create_date') or
                            fields.Datetime.now()
                        )
                        vals['name'] = self._generate_lot_serial_number(
                            product,
                            create_date,
                            reserved_names=reserved_names,
                        )

            if vals.get('name') and self._is_auto_lot_serial_name(vals['name']):
                reserved_names.add(vals['name'])

        return super(StockLot, self).create(vals_list)
