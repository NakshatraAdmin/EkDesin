# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from collections import defaultdict

class StockMove(models.Model):
    _inherit = "stock.move"

    sec_uom_id = fields.Many2one(
        "uom.uom",
        string="Secondary UoM",
        related="product_id.sec_uom_id",
        readonly=True,
    )

    secondary_product_uom_qty = fields.Float(
        string="Secondary Quantity",
        help="Secondary UoM Quantity",
        compute="_compute_secondary_product_uom_qty",
        store=True,
        readonly=False,
    )

    product_uom_qty = fields.Float(
        'Demand',
        digits='Product Unit of Measure',
        default=1.0,
        required=True,
        help="This is the quantity of product that is planned to be moved."
             "Lowering this quantity does not generate a backorder."
             "Changing this quantity on assigned moves affects "
             "the product reservation, and should be done with care.")

    show_generate_qr = fields.Boolean(compute="_compute_show_generate_qr")


    def _action_record_components(self):
        self.ensure_one()
        production = self._get_subcontract_production()[-1:]
        view = [(self.env.ref('stock.view_stock_move_operations').id, 'form')]
        # if self.env.user.has_group('base.group_portal'):
        #     view = self.env.ref('mrp_subcontracting.mrp_production_subcontracting_portal_form_view')
        context = dict(self._context)
        context.pop('skip_consumption', False)
        return {
            'name': _('Detailed Operations'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'stock.move',
            'views': view,
            'view_id': self.env.ref('stock.view_stock_move_operations').id,
            'target': 'new',
            'res_id': self.id,
            'context': dict(
                self.env.context,
            ),
        }


    @api.depends('product_id.tracking')
    def _compute_show_generate_qr(self):
        for move in self:
            move.show_generate_qr = move.product_id.tracking == 'serial' or move.product_id.tracking == 'lot'

    def action_generate_qr(self):
        for move in self:
            if not move.move_line_ids:
                continue
            for line in move.move_line_ids:
                print({
                    'Lot/Serial Number': line.lot_id.name if line.lot_id else "N/A",
                })

        return {
            'name': 'Generate QR',
            'type': 'ir.actions.act_window',
            'res_model': 'generate.qr.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('product_secondary_uom.view_generate_qr_wizard').id,
            'target': 'new',
        }

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'product_uom_qty' not in defaults:
            defaults['product_uom_qty'] = 1.0
        return defaults

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            if not self.product_uom_qty:
                self.product_uom_qty = 1.0
            # if not self.quantity:
            #     self.quantity = 1.0

    name = fields.Char(string='Description', required=True)

    @api.depends('product_uom_qty', 'product_id.sec_uom_ratio','assume_length', 'assume_width', 'assume_height')
    def _compute_secondary_product_uom_qty(self):
        for move in self:
            if move.product_id.is_need_secondary_uom and move.product_id.sec_uom_ratio:
                move.secondary_product_uom_qty = move.product_uom_qty * move.product_id.sec_uom_ratio
            else:
                move.secondary_product_uom_qty = 0.0

            if move.assume_length and move.assume_width and move.assume_height:
                move.secondary_product_uom_qty = (move.assume_length * move.assume_width * move.assume_height)*move.product_uom_qty 
            else:
                move.secondary_product_uom_qty = 0.0

    @api.onchange('secondary_product_uom_qty')
    def _onchange_secondary_product_uom_qty(self):
        for move in self:
            if move.product_id.is_need_secondary_uom and move.secondary_product_uom_qty > 0:
                if move.product_id.sec_uom_ratio:
                    move.product_uom_qty = (
                        move.secondary_product_uom_qty / move.product_id.sec_uom_ratio
                    )
            else:
                move.product_uom_qty = 0

class StockPicking(models.Model):
    _inherit = "stock.picking"

    secondary_product_uom_qty = fields.Float(
        string="Total Secondary Quantity",
        help="Total Secondary UoM Quantity from stock moves",
        compute="_compute_total_secondary_product_uom_qty",
        store=True,
    )

    @api.depends('move_ids_without_package.secondary_product_uom_qty')
    def _compute_total_secondary_product_uom_qty(self):
        for picking in self:
            picking.secondary_product_uom_qty = sum(
                move.secondary_product_uom_qty for move in picking.move_ids_without_package
            )


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    on_hand_qty = fields.Float(related="lot_id.product_qty")
    @api.model
    def _default_quant_id(self):
        if self._context.get('default_product_id'):
            quant = self.env['stock.quant'].search([
                ('product_id', '=', self._context['default_product_id']),
                ('location_id', '!=', False),
                ('quantity', '>', 0)
            ], order="quantity desc", limit=1)
            return quant.id if quant else False
        return False

    quant_id = fields.Many2one(
        'stock.quant',
        string="Pick From",
        default=_default_quant_id,
        required=True
    )
