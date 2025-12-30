{
    'name': 'Sale Order Customer Vendor Control',
    'version': '1.0',
    'depends': ['base','contacts','stock','purchase','sale'],
    'data': [
        'security/security_groups.xml',
        'security/ir_rule.xml',
        'views/sale_order_view.xml',
        'views/purchase_order_view.xml',
        'views/res_partner.xml',
    ],
    'installable': True,
}

