from odoo import api, fields, models,_
from odoo.exceptions import ValidationError, UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_customer_partner = fields.Boolean(string="Customer Partner")
    is_vendor_partner = fields.Boolean(string="Vendor Partner")
    is_internal_partner = fields.Boolean(string="Internal Partner")

    @api.model
    def create(self, vals):
        ctx = self.env.context
        if vals.get('customer_rank')==1:
            vals.setdefault('is_customer_partner', True)
        # Partner created from Purchase Order (Vendor)
        if vals.get('default_supplier_rank')==1:
            vals.setdefault('is_vendor_partner', True)
        #GST Duplicate restriction   
        vat = vals.get('vat')
        if vat not in (None, False, ''): 
            duplicate_partner = self.env['res.partner'].search([('vat','=',vat)], limit=1)
            print("====duplicate_partner===",duplicate_partner)
            if duplicate_partner:
                raise UserError(_(f"A partner {duplicate_partner[0].name}  with the same GST {vals.get('vat')} Number is already Exists."))            
        return super().create(vals)


    @api.model
    def write(self, vals):
        #GST Duplicate restriction 
        if vals.get('vat'):
            for rec in self:
                new_vat = vals.get('vat')
                duplicate_partner = self.env['res.partner'].search([('vat','=',new_vat)],limit=1)
                if duplicate_partner:
                    raise UserError(_(
                        f"A partner {duplicate_partner.name} with the same GST "
                        f"{new_vat} number already exists."
                    ))

        return super().write(vals)  



