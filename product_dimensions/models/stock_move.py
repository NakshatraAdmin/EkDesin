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

    @api.depends('product_id.width', 'product_id.length', 'product_id.height', 
                 'assume_width', 'assume_length', 'assume_height')
    def _compute_dimensions(self):
        """Compute dimensions by subtracting assumption values from product dimensions"""
        for move in self:
            # Get original product dimensions
            product_width = move.product_id.width or 0.0
            product_length = move.product_id.length or 0.0
            product_height = move.product_id.height or 0.0
            
            # Get assumption values
            assume_w = move.assume_width or 0.0
            assume_l = move.assume_length or 0.0
            assume_h = move.assume_height or 0.0
            
            # Calculate: original - assumption
            move.width = product_width - assume_w
            move.length = product_length - assume_l
            move.height = product_height - assume_h

    def _inverse_width(self):
        """Inverse method for width - allows manual editing if needed"""
        pass

    def _inverse_length(self):
        """Inverse method for length - allows manual editing if needed"""
        pass

    def _inverse_height(self):
        """Inverse method for height - allows manual editing if needed"""
        pass

    @api.onchange('assume_width', 'assume_length', 'assume_height')
    def _onchange_assume_dimensions(self):
        """Trigger recomputation when assumption fields change"""
        self._compute_dimensions()
