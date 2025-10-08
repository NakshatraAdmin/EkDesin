from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta
from odoo.fields import Command
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


class NakshatraPurchaseRequisition(models.Model):
    _name = "nakshatra.purchase.requisition"
    _description = "Purchase Requisition"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(
        required=True,
        copy=False,
        readonly=False,
        index="trigram",
        default=lambda self: _("New"),
        string="PR No.",
    )
    pr_date = fields.Date(string="Date", default=fields.Date.context_today)
    project_id = fields.Many2one("project.project", tracking=True)
    approval_request_id = fields.Many2one("approval.request")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_approve", "Under Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("partially_approved", "Partially Approved"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    line_ids = fields.One2many(
        "nakshatra.purchase.requisition.line",
        "pr_id",
        string="Lines",
        readonly=False,
        copy=True,
    )
    good_line_ids = fields.One2many(
        "nakshatra.pr.goods.line", "pr_id", string="Goods Lines", copy=True
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    location_id = fields.Many2one("stock.location", string="Location")
    reference = fields.Char()
    workorder_id = fields.Many2one("mrp.workorder")
    sale_order_id = fields.Many2one("sale.order", tracking=True)
    available_mrp_ids = fields.Many2many(
        comodel_name="mrp.production",
        compute="_compute_mrp_ids",
    )
    mrp_ids = fields.Many2many(
        "mrp.production",
        "pr_id",
        domain="[('id', 'in', available_mrp_ids)]",
        tracking=True,
        copy=True,
    )
    show_send_cancel_button = fields.Boolean(
        compute="_compute_show_send_cancel_button", store=False
    )
    hide_send_approval_btn = fields.Boolean(
        compute="_compute_hide_send_approval_btn", store=False
    )
    is_approval_required = fields.Boolean(
        compute="_compute_is_approval_required", store=False
    )
    assigned_approver_id = fields.Many2one(
        related="approval_request_id.assigned_approver_id"
    )
    approver_state = fields.Selection(related="approval_request_id.approver_state")
    admin_user_id = fields.Many2one(
        "res.users",
        string="Admin Approver",
        default=lambda self: self.env.ref("base.user_admin").id,
    )

    def check_group_permission(self):
        admin_group = self.env.ref("nakshatra_purchase_requisition.group_pr_admin")
        return self.env.user in admin_group.users or self.create_uid.id == self.env.uid

    def _explode_bom_to_dict(self, bom, multiplier, product_dict):
        for bom_line in bom.bom_line_ids:
            product = bom_line.product_id
            line_qty = bom_line.product_qty * multiplier / bom_line.bom_id.product_qty
            if product.type == "service":
                continue

            requested_qty = (
                0.0
                if product.free_qty >= line_qty or not self.sale_order_id
                else line_qty - product.free_qty
            )

            if product.id in product_dict:
                product_dict[product.id]["required_qty"] += line_qty
                product_dict[product.id]["requested_qty"] += requested_qty
            else:
                product_dict[product.id] = {
                    "product_id": product.id,
                    "required_qty": line_qty,
                    "requested_qty": requested_qty,
                    "uom_id": product.uom_id.id,
                    "project_id": self.project_id.id,
                }

            # Recursively handle nested BoMs
            child_boms = self.env["mrp.bom"]._bom_find(
                products=product, company_id=self.company_id.id
            )
            child_bom = child_boms.get(product)
            if child_bom:
                self._explode_bom_to_dict(child_bom, line_qty, product_dict)

    @api.depends("state", "line_ids.item_status")
    def _compute_hide_send_approval_btn(self):
        for rec in self:
            has_rejected_lines = any(
                line.item_status == "rejected" for line in rec.line_ids
            )
            has_zero_qty_lines = all(line.requested_qty == 0.0 for line in rec.line_ids)
            has_permission = rec.check_group_permission()

            if not has_permission or not rec.line_ids or has_zero_qty_lines:
                rec.hide_send_approval_btn = True
            elif rec.state == "draft":
                rec.hide_send_approval_btn = False
            elif (
                rec.state in ["partially_approved", "to_approve"] and has_rejected_lines
            ):
                rec.hide_send_approval_btn = False
            else:
                rec.hide_send_approval_btn = True

    def _compute_show_send_cancel_button(self):
        for rec in self:
            all_status = rec.line_ids.mapped("item_status")
            if (
                all_status
                and all(
                    s in ["cancelled", "partially_approved", "approved"]
                    for s in all_status
                )
                or not rec.line_ids
            ):
                rec.show_send_cancel_button = False
            else:
                rec.show_send_cancel_button = self.check_group_permission()

    @api.depends("project_id", "company_id")
    def _compute_mrp_ids(self):
        mrp_obj = self.env["mrp.production"]
        for pr in self:
            mrp_ids = mrp_obj.search(
                [
                    ("project_id", "=", pr.project_id.id),
                    ("company_id", "=", pr.company_id.id),
                ]
            )
            pr.available_mrp_ids = (
                mrp_ids if pr.project_id else self.env["mrp.production"]
            )

    @api.onchange("pr_date")
    def _onchange_pr_date(self):
        if self.pr_date < date.today():
            raise ValidationError(_("Backdated PR Date is not allowed."))

    def button_send_to_approval(self):
        self = self.sudo()
        all_qty = self.line_ids.mapped("requested_qty")
        if all_qty and all(s == 0.0 for s in all_qty) or not self.line_ids:
            raise ValidationError(
                _("Cannot send for approval with 0 requested qty. Please update.")
            )

        self.line_ids.filtered(lambda line: line.requested_qty == 0).unlink()
        if self.line_ids.filtered(lambda line: line.item_status == "approved"):
            self.state = "partially_approved"
        elif not self.line_ids:
            pass
        else:
            self.state = "to_approve"
        self.line_ids.filtered(
            lambda line: line.item_status
            not in ["to_approve", "approved", "partially_approved", "cancelled"]
        ).action_to_approve()

        # # create approval request
        self.action_create_approval_request()
        self.send_notification()

    # Approval Code start
    def send_notification(self):
        self = self.sudo()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref(
            "nakshatra_purchase_requisition.action_purchase_requisition_line"
        )  # Replace this with correct xml_id
        action_url = f"{base_url}/web#action={action.id}&model=nakshatra.purchase.requisition.line&view_type=list"

        for rec in self:
            if rec.approval_request_id:
                first_line = rec.approval_request_id.approval_line_ids.sorted(
                    key=lambda x: x.sequence
                )[:1]
                if first_line and first_line.primary_approver:
                    message = f"""
                            New Purchase Requisition <b>{rec.name}</b> requires your approval.<br/>
                            <a href="{action_url}" target="_blank">Click here to view</a>
                        """

                    # Send notification and email using message_notify
                    self.env["mail.thread"].message_notify(
                        partner_ids=first_line.primary_approver.partner_id.ids,
                        body=Markup(message),
                        subject="Purchase Requisition Approval Request",
                        res_id=rec.id,
                        record_name=rec.name,
                        email_layout_xmlid="mail.mail_notification_light",
                    )

                    self.env["mail.mail"].create(
                        {
                            "subject": "Purchase Requisition Approval Request",
                            "body_html": message,
                            "email_to": first_line.primary_approver.email,
                            "auto_delete": False,
                        }
                    ).send()

    def action_create_approval_request(self):
        self = self.sudo()
        for order in self:
            approval_request = self.env[
                "dynamic.approval.rule"
            ].create_approval_request(order)
            self.approval_request_id = (
                approval_request.id if approval_request else False
            )

    # Approval Code End

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                seq_date = (
                    fields.Datetime.context_timestamp(
                        self, fields.Datetime.to_datetime(vals["date_order"])
                    )
                    if "date_order" in vals
                    else None
                )
                vals["name"] = self.env["ir.sequence"].with_company(
                    vals.get("company_id")
                ).next_by_code(
                    "nakshatra.purchase.requisition", sequence_date=seq_date
                ) or _("New")

        records = super().create(vals_list)
        for rec in records:
            # If MRP IDs were set during create, process them
            if "mrp_ids" in rec._context.get("default_values", {}):
                rec._update_goods_from_mrp()
                rec._generate_lines_from_goods()
            # Also process any direct goods lines
            elif rec.good_line_ids:
                rec._generate_lines_from_goods()
        return records

    def write(self, vals):
        # Track old BOM IDs before write
        old_bom_ids = {
            rec.id: set(rec.good_line_ids.mapped("bom_id.id")) for rec in self
        }

        res = super().write(vals)

        for rec in self:
            # Only process in draft state
            if rec.state != "draft":
                continue

            # Check if mrp_ids or good_line_ids were modified
            mrp_changed = "mrp_ids" in vals
            goods_changed = "good_line_ids" in vals

            if mrp_changed:
                # First update good_line_ids based on new mrp_ids
                rec._update_goods_from_mrp()

            # Check if BOMs actually changed
            new_bom_ids = set(rec.good_line_ids.mapped("bom_id.id"))
            bom_changed = mrp_changed or (
                goods_changed and new_bom_ids != old_bom_ids.get(rec.id, set())
            )

            if bom_changed:
                # Then update line_ids based on good_line_ids, preserving manual lines
                rec._generate_lines_from_goods()

        return res

    def _clean_and_generate_lines(self):
        self.ensure_one()
        # Remove non-direct lines

        product_dict = self.get_line_product_dict()
        lines = []
        for val in product_dict.values():
            lines.append(
                {
                    "product_id": val["product_id"],
                    "required_qty": val["required_qty"],
                    "requested_qty": val["requested_qty"],
                    "approved_qty": 0.0,
                    "project_id": val["project_id"],
                    "uom_id": val["uom_id"],
                    "item_status": "draft",
                    "pr_id": self.id,
                    "is_direct_line": False,
                }
            )

        if lines:
            self.env["nakshatra.purchase.requisition.line"].create(lines)

    def _update_goods_from_mrp(self):
        """Update good_line_ids based on current mrp_ids while preserving manual BOM lines"""
        self.ensure_one()
        mrp_ids = self.mrp_ids.ids

        # Separate manual and auto-generated BOM lines
        current_auto_lines = self.good_line_ids.filtered(
            lambda line: line.is_linked_with_mrp
        )
        current_manual_lines = self.good_line_ids.filtered(
            lambda line: not line.is_linked_with_mrp
        )

        # Prepare commands for line updates
        commands = []

        # 1. Keep manual BOM lines exactly as they are
        commands.extend([(1, line.id, {}) for line in current_manual_lines])

        # 2. Remove auto lines whose BOMs are no longer in mrp_ids
        commands.extend(
            [
                (2, line.id)
                for line in current_auto_lines
                if line.mo_id.id not in mrp_ids
            ]
        )

        # 3. Add new BOMs from mrp_ids that aren't already present
        existing_mo_ids = {line.mo_id.id for line in self.good_line_ids}
        for mrp in self.mrp_ids:
            if mrp.id not in existing_mo_ids:
                commands.append(
                    (
                        0,
                        0,
                        {
                            "bom_id": mrp.bom_id.id,
                            "required_quantity": mrp.product_qty,
                            "is_linked_with_mrp": True,
                            "mo_id": mrp.id,
                        },
                    )
                )

        self.good_line_ids = commands

    def get_line_product_dict(self):
        product_dict = {}

        def _explode_bom(bom, multiplier):
            if not bom or not bom.exists():
                return

            for bom_line in bom.bom_line_ids:
                product = bom_line.product_id
                line_qty = (
                    bom_line.product_qty * multiplier / bom_line.bom_id.product_qty
                )  # Correct quantity calculation

                if product.type == "service" or set(
                    product.route_ids.mapped("name")
                ) != {"Buy"}:  # Only Buy
                    # if product.type == "service" or "Buy" not in product.route_ids.mapped('name'):
                    continue

                # Calculate requested quantity
                requested_qty = (
                    0.0
                    if product.free_qty >= line_qty or not self.sale_order_id
                    else line_qty - product.free_qty
                )

                if product.id in product_dict:
                    product_dict[product.id]["required_qty"] += line_qty
                    product_dict[product.id]["requested_qty"] += requested_qty
                else:
                    product_dict[product.id] = {
                        "product_id": product.id,
                        "required_qty": line_qty,
                        "requested_qty": requested_qty,
                        "uom_id": product.uom_id.id,
                        "project_id": self.project_id.id,
                    }

                # Find and process child BOM
                child_boms = self.env["mrp.bom"]._bom_find(
                    products=product, company_id=self.company_id.id
                )
                child_bom = child_boms.get(product)
                if child_bom and child_bom.exists():
                    _explode_bom(child_bom, line_qty)  # Pass line_qty as new multiplier

        # Process each manufacturing order
        for good_line in self.good_line_ids:
            if good_line.bom_id and good_line.required_quantity > 0:
                # Calculate initial multiplier based on MO quantity
                multiplier = good_line.required_quantity
                _explode_bom(good_line.bom_id, multiplier)

        return product_dict

    def _generate_lines_from_goods(self):
        """Generate product lines from all BOMs in good_line_ids while preserving manual lines"""
        self.ensure_one()

        # Get existing manual lines to preserve
        manual_lines = self.line_ids.filtered(lambda line: line.is_direct_line)

        # Remove only the auto-generated lines (non-direct lines)
        self.line_ids.filtered(lambda line: not line.is_direct_line).unlink()

        # Get products from all BOMs
        product_dict = self.get_line_product_dict()

        # Prepare new lines
        lines_to_create = []
        for product_id, vals in product_dict.items():
            # Check if this product already exists as a manual line
            existing_manual = manual_lines.filtered(
                lambda line: line.product_id.id == product_id
            )

            if existing_manual:
                # Update the existing manual line with BOM quantities
                existing_manual.write(
                    {
                        "required_qty": existing_manual.required_qty
                        + vals["required_qty"],
                        "requested_qty": existing_manual.requested_qty
                        + vals["requested_qty"],
                    }
                )
            else:
                # Create new auto-generated line
                lines_to_create.append(
                    {
                        "product_id": product_id,
                        "required_qty": vals["required_qty"],
                        "requested_qty": vals["requested_qty"],
                        "approved_qty": 0.0,
                        "project_id": vals["project_id"],
                        "uom_id": vals["uom_id"],
                        "item_status": "draft",
                        "pr_id": self.id,
                        "is_direct_line": False,
                    }
                )

        # Create new lines in batch
        if lines_to_create:
            self.env["nakshatra.purchase.requisition.line"].create(lines_to_create)

    def action_cancel_pr(self):
        for pr in self:
            selected_lines = pr.line_ids.filtered(lambda line: line.cancel_selected)
            if selected_lines:
                if any(
                    line.item_status in ["approved", "partially_approved"]
                    for line in selected_lines
                ):
                    raise ValidationError(
                        _("You cannot cancel lines that are already approved.")
                    )
                selected_lines.write({"item_status": "cancelled"})
            else:
                # No selection, cancel all non-approved lines
                pr.line_ids.filtered(
                    lambda line: line.item_status
                    not in ["approved", "partially_approved"]
                ).write({"item_status": "cancelled"})
            selected_lines.write({"cancel_selected": False})

            # Recompute PR state
            pr._compute_pr_state()

    def _compute_pr_state(self):
        for rec in self:
            all_status = rec.line_ids.mapped("item_status")
            if (
                all_status
                and all(s == "cancelled" for s in all_status)
                or not rec.line_ids
            ):
                rec.state = "cancelled"
            elif all(s in ["approved"] for s in all_status):
                rec.state = "approved"
            elif "to_approve" in all_status or "draft" in all_status:
                rec.state = "to_approve"
            elif all_status:
                rec.state = "partially_approved"

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft_or_cancel(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled"):
                raise UserError(
                    _(
                        "You can not delete a under approval or a approved or a partially approved purchase requisition."
                        " You must first cancel it."
                    )
                )

    def _compute_is_approval_required(self):
        for pr in self:
            pr.is_approval_required = (
                self.env["dynamic.approval.rule"].is_approval_required(
                    self.env, "nakshatra.purchase.requisition", pr.id
                )
                and pr.state == "draft"
            )

    def _onchange_manual_goods_line(self):
        product_dict = {}

        for good in self.good_line_ids.filtered(lambda g: not g.is_linked_with_mrp):
            if good.bom_id:
                self._explode_bom_to_dict(
                    good.bom_id, good.required_quantity, product_dict
                )

        # Prepare a dict of existing line_ids (only non-direct) by product_id
        existing_lines_by_product = {
            line.product_id.id: line
            for line in self.line_ids
            if not line.is_direct_line
        }

        new_commands = []

        for product_id, val in product_dict.items():
            if product_id in existing_lines_by_product:
                line = existing_lines_by_product[product_id]
                updated_required = line.required_qty + val["required_qty"]
                updated_requested = line.requested_qty + val["requested_qty"]
                new_commands.append(
                    Command.update(
                        line.id,
                        {
                            "required_qty": updated_required,
                            "requested_qty": updated_requested,
                        },
                    )
                )
            else:
                new_commands.append(
                    Command.create(
                        {
                            "product_id": val["product_id"],
                            "required_qty": val["required_qty"],
                            "requested_qty": val["requested_qty"],
                            "approved_qty": 0.0,
                            "project_id": val["project_id"],
                            "uom_id": val["uom_id"],
                            "item_status": "draft",
                            "is_direct_line": False,
                        }
                    )
                )

        if new_commands:
            # Keep existing direct lines + apply new commands
            self.line_ids = [
                Command.link(line.id) for line in self.line_ids if line.is_direct_line
            ] + new_commands

    def create_rfq_from_pr(self):
        grouped_lines = defaultdict(list)

        for line in self.line_ids:
            pr_line = line
            product = pr_line.product_id
            params = {
                "quantity": pr_line.requested_qty,
                "date": pr_line.date_planned,
            }
            seller = product._prepare_sellers(params=params)
            if not seller:
                continue  # skip if no vendor found

            vendor_id = seller[0].partner_id.id
            project_id = pr_line.pr_id.project_id.id

            if grouped_lines.get((vendor_id, project_id)) and pr_line.product_id.id in [
                line.product_id.id
                for line in grouped_lines.get((vendor_id, project_id))
            ]:
                for line in grouped_lines.get((vendor_id, project_id)):
                    if line.product_id.id == pr_line.product_id.id:
                        line += pr_line
            grouped_lines[(vendor_id, project_id)] += pr_line

        for (vendor_id, project_id), lines in grouped_lines.items():
            rfq = self.env["purchase.order"].create(
                {
                    "partner_id": vendor_id,
                    "project_id": project_id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": line.product_id.id,
                                "pr_id": line.pr_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.requested_qty,
                                "product_uom": line.product_id.uom_id.id,
                                "date_planned": line.date_planned
                                or fields.Date.today(),
                            },
                        )
                        for line in lines
                    ],
                }
            )
            # Optionally link PR lines to the RFQ
            for line in lines:
                line.write(
                    {
                        "po_id": rfq.id,
                        "item_status": "approved",
                        "approved_qty": line.requested_qty,
                    }
                )


class NakshatraPurchaseRequisitionLine(models.Model):
    _name = "nakshatra.purchase.requisition.line"
    _description = "Purchase Requisition Line"
    _rec_name = "pr_id"

    pr_id = fields.Many2one(
        "nakshatra.purchase.requisition", string="PR", ondelete="cascade"
    )
    cancel_selected = fields.Boolean(
        string="Select for Cancel", default=False, readonly=False
    )
    product_id = fields.Many2one("product.product", string="Product", required=True)
    product_code = fields.Char(related="product_id.default_code", string="Product Code")
    description = fields.Text(compute="_compute_product_desc", store=True)
    image = fields.Image(related="product_id.image_128")

    requested_qty = fields.Float(string="Requested")
    approved_qty = fields.Float(string="Approved")
    required_qty = fields.Float(string="Required")
    pending_qty = fields.Float(
        compute="_compute_pending_qty", string="Pending", store=False
    )
    received_qty = fields.Float(string="Received")
    available_qty = fields.Float(related="product_id.qty_available", string="On Hand")
    free_qty = fields.Float(related="product_id.free_qty", string="Free to Use")

    uom_id = fields.Many2one(
        "uom.uom", string="UOM", related="product_id.uom_id", readonly=True
    )
    item_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_approve", "Waiting"),
            ("partially_approved", "Partially Approved"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        string="Status",
        copy=False,
    )
    date_planned = fields.Date(string="Expected Arrival")
    company_id = fields.Many2one(
        "res.company",
        related="pr_id.company_id",
        string="Company",
        store=True,
        readonly=True,
    )
    pr_date = fields.Date(related="pr_id.pr_date")
    project_id = fields.Many2one(related="pr_id.project_id")
    reject_reason = fields.Text(string="Rejection Reason")
    po_id = fields.Many2one("purchase.order", string="Related PO")
    po_datetime = fields.Datetime(related="po_id.date_order")
    picking_id = fields.Many2one("stock.picking", string="GRN No")
    picking_datetime = fields.Datetime(related="picking_id.scheduled_date")
    pr_state = fields.Selection(related="pr_id.state", string="PR Status")
    pr_reference = fields.Char(related="pr_id.reference")
    pr_mrp_ids = fields.Many2many(related="pr_id.mrp_ids")
    is_direct_line = fields.Boolean()
    manual_line_id = fields.Many2one(
        "nakshatra.pr.goods.line",
        string="Linked BOM Line",
        help="Links to the BOM line that generated this product line",
    )
    assigned_approver_id = fields.Many2one(related="pr_id.assigned_approver_id")
    approver_state = fields.Selection(related="pr_id.approver_state")
    admin_user_id = fields.Many2one(
        "res.users",
        string="Admin Approver",
        default=lambda self: self.env.ref("base.user_admin").id,
    )

    @api.depends("product_id")
    def _compute_product_desc(self):
        for rec in self:
            rec.description = rec.product_id.description_purchase
            # Only set is_direct_line if it's not already set
            if rec.is_direct_line is not True:
                rec.is_direct_line = rec.required_qty == 0

    @api.depends("product_id")
    def _compute_product_desc(self):
        for rec in self:
            rec.description = rec.product_id.description_purchase
            rec.is_direct_line = True if rec.required_qty == 0 else False

    @api.depends("requested_qty", "received_qty")
    def _compute_pending_qty(self):
        for line in self:
            line.pending_qty = (line.requested_qty or 0.0) - (line.received_qty or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # If expected_date not passed, calculate from PR lead time
            if not vals.get("date_planned"):
                lead_days = self.env.company.pr_lead or 0.0
                vals["date_planned"] = (
                    datetime.today() + timedelta(days=lead_days)
                ).date()
        return super(NakshatraPurchaseRequisitionLine, self).create(vals_list)

    def action_to_approve(self):
        for rec in self:
            if rec.item_status != "approved":
                rec.update({"item_status": "to_approve"})

    def send_rejection_notification(self, pr_id, action_by, state):
        """Notify the PR request owner via in-app and email when approval is rejected/approved"""

        approval_request = pr_id.approval_request_id
        owner = approval_request.request_owner_id

        if not approval_request or not owner or not owner.partner_id:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        action = self.env.ref(
            "nakshatra_purchase_requisition.action_purchase_requisition_line"
        )
        action_url = f"{base_url}/web#action={action.id}&model=nakshatra.purchase.requisition.line&view_type=list"

        # Message content
        message = (
            f"Purchase Requisition <b>{pr_id.name}</b> has been <b>{state.upper()}</b> by <b>{action_by.name}</b>.<br/>"
            f"<a href='{action_url}' target='_blank'>View Requisition Lines</a>"
        )

        # In-app notification
        self.env["mail.thread"].message_notify(
            body=Markup(message),
            subject="Approval Update",
            partner_ids=[owner.partner_id.id],
            res_id=pr_id.id,
            record_name=pr_id.name,
            email_layout_xmlid="mail.mail_notification_light",
        )

        # Plain email
        if owner.email:
            self.env["mail.mail"].create(
                {
                    "subject": f"Approval Update - {pr_id.name}",
                    "body_html": f"<p>{message}</p>",
                    "email_to": owner.email,
                    "auto_delete": True,
                    "author_id": self.env.user.partner_id.id,
                }
            ).send()

    def action_approve_reject_items(self):
        if self.filtered(lambda line: line.item_status != "to_approve"):
            raise UserError(_("Please select only waiting items."))
        action = {
            "type": "ir.actions.act_window",
            "res_model": "pr.line.approval.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_ids": self.ids},
        }
        return action

    def check_user_is_approver(self):
        """
        Checks if the current user is assigned as a primary or secondary approver
        for the related approval request. Raises UserError if not.
        """
        current_user = self.env.user
        approval_lines = self.pr_id.approval_request_id.approval_line_ids

        if not approval_lines:
            raise UserError(_("No approval lines found for this request."))

        is_approver = any(
            line.primary_approver.id == current_user.id
            or line.secondary_approver.id == current_user.id
            for line in approval_lines
        )

        if not is_approver:
            raise UserError(_("You are not assigned as an approver for this request."))

    def action_reject_all_items(self):
        self = self.sudo()
        # Check if any items are waiting for approval
        self.check_user_is_approver()

        if self.filtered(lambda line: line.item_status != "to_approve"):
            raise UserError(_("Please select only waiting items."))
        for line in self:
            msg_post = "Rejected: %s , Qty: %s : %s\n" % (
                line.product_id.name,
                line.requested_qty,
                "",
            )
            line.item_status = "rejected"
            line.pr_id.message_post(body=msg_post)

            # Send rejection notification
            self.send_rejection_notification(line.pr_id, self.env.user, "rejected")

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        if self._check_line_unlink():
            raise UserError(
                _(
                    "Once a purchase requisition is send for approval, you can't remove one of its lines."
                )
            )

    def _check_line_unlink(self):
        return self.filtered(lambda line: line.item_status != "draft")


class PRGoodsLine(models.Model):
    _name = "nakshatra.pr.goods.line"
    _description = "PR Goods Line (BoM Based)"

    pr_id = fields.Many2one(
        "nakshatra.purchase.requisition", string="PR", ondelete="cascade"
    )
    bom_id = fields.Many2one("mrp.bom", string="BoM", required=True)
    required_quantity = fields.Float(default=1.0, readonly=False)
    is_linked_with_mrp = fields.Boolean(default=False)
    mo_id = fields.Many2one("mrp.production")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for line in records:
            if not line.is_linked_with_mrp:
                line.pr_id._generate_lines_from_goods()
        return records

    def write(self, vals):
        res = super().write(vals)
        for line in self:
            self.pr_id._generate_lines_from_goods()
            if not line.is_linked_with_mrp:
                line.pr_id._onchange_manual_goods_line()
        return res

    def unlink(self):
        pr_id = self.pr_id
        res = super().unlink()
        pr_id._generate_lines_from_goods()
        return res
