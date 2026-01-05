# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError



class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    show_dimensions = fields.Boolean(
        related="product_id.show_dimensions",
        readonly=True,
        store=True,
    )

    width = fields.Float(
        related="product_id.width",
        readonly=False,
        store=True,
    )
    length = fields.Float(
        related="product_id.length",
        readonly=False,
        store=True,
    )
    height = fields.Float(
        related="product_id.height",
        readonly=False,
        store=True,
    )
    original_width = fields.Float(
        string="Width",
        store=True,
        readonly=False,
    )
    original_length = fields.Float(
        string="Length",
        store=True,
        readonly=False,
    )
    original_height = fields.Float(
        string="Height",
        store=True,
        readonly=False,
    )

    assume_width = fields.Float(
        string="Actual Width",
        digits='Product Unit of Measure',
    )
    assume_length = fields.Float(
        string="Actual Length",
        digits='Product Unit of Measure',
    )
    assume_height = fields.Float(
        string="Actual Height",
        digits='Product Unit of Measure',
    )

