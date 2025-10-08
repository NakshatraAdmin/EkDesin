from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = "project.project"

    sale_order_id = fields.Many2one("sale.order", string="Related Sale Order")
    purchase_order_id = fields.Many2one(
        "purchase.order", string="Related Purchase Order"
    )

    mrp_production_count = fields.Integer(
        string="MO Count",
        related="sale_order_id.mrp_production_count",
        readonly=True,
    )
    purchase_order_count = fields.Integer(
        string="PO Count",
        compute="_compute_purchase_order_count",
        readonly=True,
    )
    invoice_count = fields.Integer(
        string="Invoice Count",
        related="sale_order_id.invoice_count",
        readonly=True,
        groups="base.group_user",
    )
    vendor_bill_count = fields.Integer(
        string="Vendor Bill Count",
        related="purchase_order_id.invoice_count",
        readonly=True,
        groups="base.group_user",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Project Warehouse",
        readonly=True,
        help="Warehouse automatically created for this project",
    )
    purchase_requisition_count = fields.Integer(
        string="Purchase Requisitions", compute="_compute_purchase_requisition_count"
    )

    def _compute_purchase_requisition_count(self):
        for project in self:
            project.purchase_requisition_count = self.env[
                "nakshatra.purchase.requisition"
            ].search_count([("project_id", "=", project.id)])

    def _compute_purchase_order_count(self):
        for project in self:
            project.purchase_order_count = self.env["purchase.order"].search_count(
                [("project_id", "=", project.id)]
            )

    def action_view_purchase_requisitions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Purchase Requisitions",
            "res_model": "nakshatra.purchase.requisition",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id},
            "target": "current",
        }

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        for project in projects:
            try:
                project._create_project_warehouse()
            except Exception as e:
                _logger.warning(
                    f"Failed to create warehouse for project {project.name}: {str(e)}"
                )

        return projects

    def _create_project_warehouse(self):
        self.ensure_one()

        if self.warehouse_id:
            return

        warehouse_vals = {
            "name": f"WH-{self.name}",
            "code": f"PRJ-{self.id}",
        }
        warehouse = self.env["stock.warehouse"].create(warehouse_vals)
        self.warehouse_id = warehouse.id

        return warehouse

    def action_view_warehouse(self):
        self.ensure_one()
        if not self.warehouse_id:
            return {"type": "ir.actions.act_window_close"}

        return {
            "type": "ir.actions.act_window",
            "name": "Project Warehouse",
            "res_model": "stock.warehouse",
            "res_id": self.warehouse_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_project_purchase_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Purchase Orders",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id},
            "target": "current",
        }

    def action_view_invoice(self):
        self.ensure_one()
        if not self.sale_order_id:
            return {"type": "ir.actions.act_window_close"}

        return self.sale_order_id.action_view_invoice()

    def action_view_vendor_bills(self):
        self.ensure_one()
        if not self.purchase_order_id:
            return {"type": "ir.actions.act_window_close"}

        return self.purchase_order_id.action_view_invoice()
