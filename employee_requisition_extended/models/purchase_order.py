# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrderExtended(models.Model):
    """Extended Purchase Order to link back to Employee Requisition"""
    _inherit = 'purchase.order'

    # Add Many2one field to link back to employee requisition
    employee_requisition_id = fields.Many2one(
        comodel_name='employee.purchase.requisition',
        string='Source Requisition',
        help='Employee Purchase Requisition that created this RFQ/Purchase Order',
        ondelete='set null',
        index=True
    )
