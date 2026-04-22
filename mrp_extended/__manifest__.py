{
    "name": "Extend - Manufacturing",
    "version": "1.0",
    "summary": "Manufacturing Extention for Odoo 18",
    "author": "Nakshatra",
    "category": "Manufacturing",
    "depends": ['mrp', 'product_dimensions', 'lot_serial_auto_generation'],
    "data": [
        "views/mrp_bom_views.xml",
        "views/mrp_production_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}
