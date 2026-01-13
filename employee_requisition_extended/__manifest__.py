# -*- coding: utf-8 -*-
{
    'name': 'Employee Requisition Extended',
    'version': '18.0.1.0.0',
    'category': 'Purchases',
    'summary': 'Form-level request type toggle and business rules for Material/Purchase Requisitions',
    'description': """
        This module extends employee_purchase_requisition to add:
        1. Form-level request type toggle (Material Requisition / Purchase Requisition)
        2. Security group for PR creation control
        3. Business rules: 
           - MR (Material Requisition): Creates Internal Transfer only
           - PR (Purchase Requisition): Creates both PO and Internal Transfer
    """,
    'author': 'EkDesin',
    'depends': ['base', 'hr', 'stock', 'purchase', 'employee_purchase_requisition', 'project'],
    'data': [
        'security/requisition_extended_groups.xml',
        'security/ir.model.access.csv',
        'views/employee_purchase_requisition_views.xml',
        'views/employee_purchase_requisition_menu.xml',
        'views/requisition_order_views.xml',
        'report/employee_purchase_requisition_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
