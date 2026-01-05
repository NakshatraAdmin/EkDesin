{
    "name": "Product Dimensions",
    "summary": "Product Dimensions Management",
    "description": """
        This module adds dimension fields (width, length, height) to products.
        When show_dimensions is enabled, these fields are visible in:
        - Purchase Orders
        - Purchase Order Receipts (with assumption fields)
        - Manufacturing Orders (with assumption fields)
    """,
    "author": "",
    "website": "",
    "license": "LGPL-3",
    "category": "Inventory",
    "version": "18.0.1.0.0",
    "depends": ["purchase", "mrp", "stock", "product_secondary_uom"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template.xml",
        "views/product_views.xml",
        "views/purchase_order_views.xml",
        "views/stock_move_line_views.xml",
        "views/mrp_production_views.xml",
        "views/mrp_bom.xml",
    ],
}
