{
    "name": "sale Order Custom Report",
    "version": "1.0",
    "summary": "Custom Sale Order PDF report (QWeb) for Odoo 18",
    "author": "Nakshatra",
    "category": "Sale",
    "depends": ["sale","web"],
    "data": [
    	'security/ir.model.access.csv',
        "views/report_sale_order.xml",
        "views/sale_order_pdf.xml",
         "views/report_sale_fotter.xml",
	"wizard/cancel_reason_wizard.xml"
    ],
    "assets": {
        "web.report_assets_pdf": [
            "sale_order_custom_report/static/src/css/sale_report.css"
        ]
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}

