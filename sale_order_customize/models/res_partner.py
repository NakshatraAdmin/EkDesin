from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_customer_partner = fields.Boolean(string="Customer Partner")
    is_vendor_partner = fields.Boolean(string="Vendor Partner")
    is_internal_partner = fields.Boolean(string="Internal Partner")

    @api.model
    def create(self, vals):
        # tttt
        ctx = self.env.context
        print("====",vals,ctx.get('default_customer_rank'))
        # ggggg
        # Partner created from Sale Order (Customer)
        if vals.get('customer_rank')==1:
            vals.setdefault('is_customer_partner', True)
        # Partner created from Purchase Order (Vendor)
        if vals.get('default_supplier_rank')==1:
            vals.setdefault('is_vendor_partner', True)

        return super().create(vals)
