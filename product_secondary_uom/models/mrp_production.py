# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    sec_uom_id = fields.Many2one(
        "uom.uom",
        string="Secondary UoM",
        related="product_id.sec_uom_id",
        readonly=True,
    )

    # secondary_product_uom_qty = fields.Float(
    #     string="Secondary Quantity",
    #     help="Secondary UoM Quantity",
    #     compute="_compute_secondary_product_uom_qty",
    #     store=True,
    # )

    weight = fields.Float(
        string="Weight",
        related="product_id.weight",
        store=True,
        readonly=False,
    )
    height = fields.Float(
        string="Height",
        # related="product_id.height",
        store=True,
        readonly=False,
    )
    length = fields.Float(
        string="Length",
        related="product_id.length",
        store=True,
        readonly=False,
    )
    width = fields.Float(
        string="Width",
        related="product_id.width",
        store=True,
        readonly=False,
    )
    depth = fields.Float(
        string="Depth",
        related="product_id.depth",
        store=True,
        readonly=False,
    )

    # @api.depends('move_raw_ids.product_uom_qty', 'move_raw_ids.product_id.sec_uom_ratio','move_raw_ids.length','move_raw_ids.width','move_raw_ids.height',)
    # def _compute_secondary_product_uom_qty(self):
    #     for record in self:
    #         for move in record.move_raw_ids:
    #             if move.product_id and move.product_id.sec_uom_ratio > 0 and move.product_uom_qty > 0:
    #                 move.secondary_product_uom_qty = move.product_uom_qty * move.product_id.sec_uom_ratio
    #             else:
    #                 move.secondary_product_uom_qty = 0.0
    #             if move.length and move.width and move.height:
    #                 move.secondary_product_uom_qty = (move.length * move.width * move.height)*move.product_uom_qty 
                # else:
                #     move.secondary_product_uom_qty = 0.0


    @api.onchange('product_id','length','width','height')
    def _onchange_product_id(self):
        self.action_compute_secondary_quantity()

    def action_compute_secondary_quantity(self):
        for record in self:
            for move in record.move_raw_ids:
                if move.product_id and move.product_id.sec_uom_ratio > 0 and move.product_uom_qty > 0:
                    move.secondary_product_uom_qty = move.product_uom_qty * move.product_id.sec_uom_ratio
                else:
                    move.secondary_product_uom_qty = 0.0
                if move.length and move.width and move.height:
                    move.secondary_product_uom_qty = (move.length * move.width * move.height)*move.product_uom_qty 
                # else:
                #     move.secondary_product_uom_qty = 0.0


    def _prepare_stock_lot_values(self):
        self.ensure_one()
        name = self.env['ir.sequence'].next_by_code('stock.lot.serial')
        last_lot = self.env['stock.lot'].search([], order='id desc', limit=1)
        last_lot_number = str(int(last_lot.name) + 1) if last_lot and last_lot.name.isdigit() else "1"
        exist_lot = not last_lot_number or self.env['stock.lot'].search([
            ('product_id', '=', self.product_id.id),
            ('company_id', '=', self.company_id.id),
            ('name', '=', last_lot_number),
        ], limit=1)
        if exist_lot:
            name = self.env['stock.lot']._get_next_serial(self.company_id, self.product_id)
        if not name:
            raise UserError(_("Please set the first Serial Number or a default sequence"))
        return {
            'product_id': self.product_id.id,
            'company_id': self.company_id.id,
            'name': last_lot_number,
        }


class StockMove(models.Model):
    _inherit = 'stock.move'

    secondary_product_uom_qty = fields.Float(
        string="Secondary UoM Quantity",
        help="The quantity in the secondary unit of measure."
    )

    consumption_uom_id = fields.Many2one(
        "uom.uom",
        string="Consumption UoM",
        related="product_id.consumption_uom_id",
        store=True,
    )

    consumption_product_uom_qty = fields.Float(
        string="Consumption Quantity",
        help="Select the Consumption UoM Quantity",
        store=True,
    )

    sec_uom_ratio = fields.Float(
        related="product_id.sec_uom_ratio",
        string="Secondary UoM Ratio",
        readonly=True,
        help="The conversion ratio between the secondary and main unit of measure for the product."
    )

    weight = fields.Float(
        string="Weight",
        related="product_id.weight",
        store=True,
        readonly=False,
    )
    height = fields.Float(
        string="Height",
        # related="product_id.height",
        store=True,
        readonly=False,
    )
    length = fields.Float(
        string="Length",
        # related="product_id.length",
        store=True,
        readonly=False,
    )
    width = fields.Float(
        string="Width",
        # related="product_id.width",
        store=True,
        readonly=False,
    )
    depth = fields.Float(
        string="Depth",
        # related="product_id.depth",
        store=True,
        readonly=False,
    )
    assume_width = fields.Float(
        string="Actual Width",
        help="Assumed width value (editable)",
        digits='Product Unit of Measure',
    )
    assume_length = fields.Float(
        string="Actual Length",
        help="Assumed length value (editable)",
        digits='Product Unit of Measure',
    )
    assume_height = fields.Float(
        string="Actual Height",
        help="Assumed height value (editable)",
        digits='Product Unit of Measure',
    )

    # @api.onchange('secondary_product_uom_qty')
    # def _onchange_secondary_product_uom_qty(self):
    #     if self.product_id and self.product_id.is_need_secondary_uom and self.secondary_product_uom_qty > 0:
    #         if self.product_id.sec_uom_ratio:
    #             self.product_uom_qty = self.secondary_product_uom_qty / self.product_id.sec_uom_ratio
    #         else:
    #             self.product_uom_qty = 0.0
    #     else:
    #         self.product_uom_qty = 0.0

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty(self):
        if self.product_id and self.product_id.is_need_secondary_uom and self.product_uom_qty > 0:
            if self.product_id.sec_uom_ratio:
                self.secondary_product_uom_qty = self.product_uom_qty * self.product_id.sec_uom_ratio
            else:
                self.secondary_product_uom_qty = 0.0
        else:
            self.secondary_product_uom_qty = 0.0

    @api.onchange('consumption_product_uom_qty')
    def _onchange_consumption_product_uom_qty(self):
        if self.product_id and self.product_id.is_need_consumption_uom and self.consumption_product_uom_qty > 0:
            if self.product_id.consumption_uom_ratio:
                self.product_uom_qty = self.consumption_product_uom_qty / self.product_id.consumption_uom_ratio
            else:
                self.product_uom_qty = 0.0
        else:
            self.product_uom_qty = 0.0

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty(self):
        if self.product_id and self.product_id.is_need_consumption_uom and self.product_uom_qty > 0:
            if self.product_id.consumption_uom_ratio:
                self.consumption_product_uom_qty = self.product_uom_qty * self.product_id.consumption_uom_ratio
            else:
                self.consumption_product_uom_qty = 0.0
        else:
            self.consumption_product_uom_qty = 0.0