{
    "name": "Purchase Order Custom Report",
    "version": "1.0",
    "summary": "Custom Purchase Order PDF report (QWeb) for Odoo 18",
    "author": "ChatGPT",
    "category": "Purchases",
    "depends": ["purchase","web"],
    "data": [
        "views/report_purchase_order.xml",
        "views/purchase_order_pdf.xml",
         "views/report_purchase_fotter.xml"
    ],
    "assets": {
        "web.report_assets_pdf": [
            "purchase_order_custom_report/static/src/css/purchase_report.css"
        ]
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}

