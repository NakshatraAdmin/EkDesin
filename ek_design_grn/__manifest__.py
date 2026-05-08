{
    "name": "GRN Custom Report",
    "version": "1.0",
    "summary": "Custom GRN for Odoo 18",
    "author": "Nakshatra",
    "category": "Purchases",
    "depends": ["stock","web",'project','product_dimensions','mrp'],
    "data": [
        "views/report_grn_document_action.xml",
        "views/report_grn_document.xml",
        "views/report_material_issue_slip_action.xml",
        "views/report_material_issue_slip.xml",
        "views/stock_picking.xml"
    ],
    "assets": {
        "web.report_assets_pdf": [
            "ek_design_grn/static/src/css/purchase_report.css"
        ]
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}
