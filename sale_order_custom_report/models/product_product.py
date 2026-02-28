from odoo import models, fields


from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_comment = fields.Html(
        string="Product Comment",
        help="This comment will appear in Sale Order PDF"
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    product_comment = fields.Html(
        string="Product Comment",
        help="This comment will appear in Sale Order PDF"
    )
