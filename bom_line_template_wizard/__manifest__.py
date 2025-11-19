{
    "name": "BOM Line - Product Template + Wizard",
    "version": "18.0.0.1",
    "summary": "Add product.template field to BOM lines and open a select-template wizard.",
    "category": "Manufacturing",
    "author": "You",
    "depends": ["mrp", "product"],
    "data": [
        "views/bom_line_template_wizard_views.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False
}
