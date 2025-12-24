{
    "name": "Material Issue Slip PDF",
    "version": "18.0.1.0.0",
    "category": "Inventory",
    "summary": "Exact Material Issue Slip PDF for Pick Components",
    "depends": ["stock", "mrp"],
    "data": [
        # "security/ir.model.access.csv",
        "report/material_issue_slip_pdf.xml",
        "report/report_action.xml",
        "views/picking_view.xml",
    ],
    "installable": True,
    "application": False,
}

