{
    'name': 'MO BOM Components Viewer',
    'version': '1.0',
    'summary': 'Show BOM product list in Manufacturing Order',
    'description': """
Displays all BOM components directly on the Manufacturing Order form.
""",
    'author': 'Nakshatra',
    'depends': ['mrp'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/mrp_production_view.xml',
    ],
    'installable': True,
    'application': False,
}

