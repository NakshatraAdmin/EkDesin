# -*- coding: utf-8 -*-

from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    # show_dimensions is inherited from product.template via _inherits
    # No additional fields needed here
