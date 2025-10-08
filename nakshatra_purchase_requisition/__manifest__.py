{
    "name": "Nakshatra Purchase Requisition",
    "version": "18.0.1.0.0",
    "category": "Purchases",
    "summary": "Custom PR flow for Nakshatra project",
    "author": "7Span",
    "website": "https://7span.com/",
    "depends": [
        "base",
        "purchase",
        "project",
        "mrp",
        "sale_stock",
        "dynamic_approval_rule",
    ],
    "license": "LGPL-3",
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/purchase_requisition_sequence.xml",
        "data/server_action.xml",
        "data/rules.xml",
        "views/purchase_requisition_views.xml",
        "views/res_config_settings_views.xml",
        "views/purchase_views.xml",
        "views/sale_views.xml",
        "report/report_purchase_reuquisition.xml",
        "report/pr_tracking_report.xml",
        "report/ir_actions_report.xml",
        "wizards/pr_line_approval_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "nakshatra_purchase_requisition/static/src/xml/mrp_menu_dialog.xml"
        ],
    },
}
