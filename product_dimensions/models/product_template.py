# -*- coding: utf-8 -*-

from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    show_dimensions = fields.Boolean(
        string="Show Dimensions",
        help="When checked, width, length, and height fields will be visible in Purchase Orders, Receipts, and Manufacturing Orders",
        default=False,
    )
