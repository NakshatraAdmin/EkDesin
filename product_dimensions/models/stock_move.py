# -*- coding: utf-8 -*-

from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = "stock.move"

    # Dimension fields - for PO receipts and MO
    show_dimensions = fields.Boolean(
        string="Show Dimensions",
        related="product_id.show_dimensions",
        readonly=True,
        store=True,
    )
    width = fields.Float(
        string="Width",
        compute="_compute_dimensions",
        inverse="_inverse_width",
        store=True,
        readonly=False,
    )
    length = fields.Float(
        string="Length",
        compute="_compute_dimensions",
        inverse="_inverse_length",
        store=True,
        readonly=False,
    )
    height = fields.Float(
        string="Height",
        compute="_compute_dimensions",
        inverse="_inverse_height",
        store=True,
        readonly=False,
    )
    sec_uom = fields.Char(
        string="UoM", 
        readonly=True, default="ft²")
    
    # Assumption fields - editable by user (for PO receipts and MO)
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
    
    cubic_ft = fields.Float(
        string="Cubic Feet",
        compute="_compute_cubic_ft",
        store=True,
        help="Cubic feet calculated from dimensions (Length * Width * Height)",
    )
    dary_product_uom_qty = fields.Float(string="All Quantity")

    base_length = fields.Float(string="Base Length", default=0.0)
    base_width = fields.Float(string="Base Width", default=0.0)
    base_height = fields.Float(string="Base Height", default=0.0)



    @api.depends(
    'base_length', 'base_width', 'base_height',
    'assume_length', 'assume_width', 'assume_height'
    )
    def _compute_dimensions(self):
        pass

    def _inverse_width(self):
        """Inverse method for width - allows manual editing if needed"""
        pass

    def _inverse_length(self):
        """Inverse method for length - allows manual editing if needed"""
        pass

    def _inverse_height(self):
        """Inverse method for height - allows manual editing if needed"""
        pass

    @api.onchange('assume_width', 'assume_length', 'assume_height','length','width','height')
    def _onchange_assume_dimensions(self):
        """Trigger recomputation when assumption fields change"""
        self._compute_dimensions()
        self._compute_cubic_ft()

    @api.depends('length', 'width', 'height')
    def _compute_cubic_ft(self):
        """Calculate cubic feet from dimensions"""
        for move in self:
            if move.length and move.width and move.height:
                move.cubic_ft = move.length * move.width * move.height
            else:
                move.cubic_ft = 0.0