# -*- coding: utf-8 -*-

from odoo import models, fields


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
        related="product_id.width",
        store=True,
        readonly=False,
    )
    length = fields.Float(
        string="Length",
        related="product_id.length",
        store=True,
        readonly=False,
    )
    height = fields.Float(
        string="Height",
        related="product_id.height",
        store=True,
        readonly=False,
    )
    
    # Assumption fields - editable by user (for PO receipts and MO)
    assume_width = fields.Float(
        string="Assume Width",
        help="Assumed width value (editable)",
        digits='Product Unit of Measure',
    )
    assume_length = fields.Float(
        string="Assume Length",
        help="Assumed length value (editable)",
        digits='Product Unit of Measure',
    )
    assume_height = fields.Float(
        string="Assume Height",
        help="Assumed height value (editable)",
        digits='Product Unit of Measure',
    )
