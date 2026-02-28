from odoo import api, fields, models, _
from odoo.exceptions import UserError


from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SelectProductTemplateWizard(models.TransientModel):
    _name = "select.product.template.wizard"
    _description = "Select Product Template for BOM Line"

    product_tmpl_id = fields.Many2one(
        "product.template", string="Product Template", required=True,
        domain=[("sale_ok", "=", True)]
    )
    attribute_value_ids = fields.Many2many(
        "product.attribute.value",
        string="Attribute Values",
        help="Choose attribute values to filter/select variants (matches variants that contain ALL selected values)."
    )
    product_ids = fields.Many2many("product.product", string="Product Variants")
    create_variant = fields.Boolean(
        string="Create Variant if Not Exists", default=True
    )
    qty = fields.Float(string="Quantity", default=1.0)
    product_uom_id = fields.Many2one("uom.uom", string="UoM")
    bom_line_id = fields.Many2one("mrp.bom.line", string="BOM Line")
    bom_id = fields.Many2one("mrp.bom", string="BOM")

    # Helper: normalize attribute values for a variant across Odoo versions
    def _get_variant_attribute_values(self, product):
        AttrVal = self.env["product.attribute.value"]
        if not product:
            return AttrVal.browse()
        if hasattr(product, "attribute_value_ids"):
            return product.attribute_value_ids or AttrVal.browse()
        if hasattr(product, "product_template_attribute_value_ids"):
            return product.product_template_attribute_value_ids.mapped("product_attribute_value_id")
        return AttrVal.browse()

    # -------------------------
    # Default and onchanges
    # -------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = dict(self._context or {})
        if ctx.get("default_bom_line_id"):
            bline = self.env["mrp.bom.line"].browse(ctx.get("default_bom_line_id"))
            if bline and bline.exists():
                res.setdefault("bom_line_id", bline.id)
                res.setdefault("bom_id", bline.bom_id.id)
                if bline.product_id:
                    res.setdefault("product_ids", [(6, 0, [bline.product_id.id])])
                    # prefill attribute values for that product variant using helper
                    try:
                        vals = self._get_variant_attribute_values(bline.product_id)
                        if vals:
                            res.setdefault("attribute_value_ids", [(6, 0, vals.ids)])
                    except Exception:
                        pass
                if bline.product_qty is not None:
                    res.setdefault("qty", bline.product_qty)
                if bline.product_uom_id:
                    res.setdefault("product_uom_id", bline.product_uom_id.id)
                if bline.product_tmpl_id:
                    res.setdefault("product_tmpl_id", bline.product_tmpl_id.id)
        elif ctx.get("default_bom_id"):
            res.setdefault("bom_id", ctx.get("default_bom_id"))
            if ctx.get("default_product_tmpl_id"):
                res.setdefault("product_tmpl_id", ctx.get("default_product_tmpl_id"))
            if ctx.get("default_qty") is not None:
                res.setdefault("qty", ctx.get("default_qty"))
        if ctx.get("default_product_tmpl_id") and not res.get("product_tmpl_id"):
            res.setdefault("product_tmpl_id", ctx.get("default_product_tmpl_id"))
        return res

    @api.onchange("product_tmpl_id")
    def _onchange_product_tmpl(self):
        """When template chosen, restrict attribute values and variants to template only."""
        if self.env.context.get('active_model') == 'product.template':
            self.product_tmpl_id = self.env.context.get('active_id')
        
        # This will clear the Attribute Values field when the Product Template changes
        self.attribute_value_ids = False
        
        # Return a dynamic domain to filter the attribute values
        domain = []
        if self.product_tmpl_id:
            # Get all attribute value IDs from the selected product template's attribute lines
            attribute_value_ids = self.product_tmpl_id.attribute_line_ids.mapped('value_ids')
            print("===attribute_value_ids",attribute_value_ids)
            # ssssssssss
            # domain = [('id', 'in', attribute_value_ids.ids)]

            self.attribute_value_ids=[(6, 0, attribute_value_ids.ids)]

    


    @api.onchange("attribute_value_ids")
    def _onchange_attribute_values(self):
        """Only filter variants; DO NOT create anything here (creation is done on Apply)."""
        if not self.product_tmpl_id:
            self.product_ids = [(5, 0, 0)]
            return

        ProductProduct = self.env["product.product"]
        candidates = ProductProduct.search([("product_tmpl_id", "=", self.product_tmpl_id.id)])
        if not self.attribute_value_ids:
            self.product_ids = [(6, 0, candidates.ids)]
            return {"domain": {"product_ids": [("product_tmpl_id", "=", self.product_tmpl_id.id)]}}

        selected_ids = set(self.attribute_value_ids.ids)
        matched = candidates.filtered(
            lambda p: selected_ids.issubset(set(self._get_variant_attribute_values(p).ids))
        )
        # show matched variants (if any) in product_ids; do not create here
        self.product_ids = [(6, 0, matched.ids)]
        return {"domain": {"product_ids": [("product_tmpl_id", "=", self.product_tmpl_id.id)]}}

    # -------------------------
    # Safety helper: ensure PTAL & PTAV exist, create variant safely
    # -------------------------
    def _ensure_ptal_and_ptav_for_values(self, template, attr_values):
        """
        Ensure existence of:
          - product.template.attribute.line (PTAL) for each attribute,
          - product.template.attribute.value (PTAV) for each selected attribute value.
        Returns list of PTAV ids (integers).
        """
        TemplateAttrLine = self.env["product.template.attribute.line"].sudo()
        TemplateAttrValue = self.env["product.template.attribute.value"].sudo()

        ptav_ids = []
        for val in attr_values:
            # 1) PTAL: ensure exists
            line = TemplateAttrLine.search([
                ("product_tmpl_id", "=", template.id),
                ("attribute_id", "=", val.attribute_id.id)
            ], limit=1)
            if not line:
                line = TemplateAttrLine.create({
                    "product_tmpl_id": template.id,
                    "attribute_id": val.attribute_id.id,
                })
            # ensure value is present on line.value_ids (use write with (4,val.id))
            if val.id not in line.value_ids.ids:
                line.write({"value_ids": [(4, val.id)]})

            # 2) PTAV: ensure exists and set product_attribute_value_id and attribute_line_id
            ptav = TemplateAttrValue.search([
                ("product_tmpl_id", "=", template.id),
                ("product_attribute_value_id", "=", val.id)
            ], limit=1)
            if not ptav:
                ptav = TemplateAttrValue.create({
                    "product_tmpl_id": template.id,
                    "attribute_id": val.attribute_id.id,
                    "product_attribute_value_id": val.id,
                    "attribute_line_id": line.id,
                })
            # collect integer id
            ptav_ids.append(ptav.id)
        return ptav_ids

    # -------------------------
    # ACTION: Apply (create on explicit user action)
    # -------------------------
    def action_apply_to_bom_line(self):
        """When user clicks Apply: create variant if needed and update/create BOM lines."""
        self.ensure_one()
        if not self.product_tmpl_id:
            raise UserError(_("Please select a Product Template."))

        ProductProduct = self.env["product.product"].sudo()

        # 1) Use selected products if any
        variants = self.product_ids.sorted(key=lambda r: r.id) if self.product_ids else self.env["product.product"]

        # 2) No products but attribute values selected
        if not self.product_ids and self.attribute_value_ids:
            candidates = self.env["product.product"].search([
                ("product_tmpl_id", "=", self.product_tmpl_id.id)
            ])
            selected_ids = set(self.attribute_value_ids.ids)
            matched = candidates.filtered(
                lambda p: selected_ids.issubset(set(self._get_variant_attribute_values(p).ids))
            )
            if matched:
                variants = matched
            else:
                # Create variant
                if self.create_variant:
                    template = self.product_tmpl_id
                    print("=====template",template.name)

                    ptav_ids = self._ensure_ptal_and_ptav_for_values(template, self.attribute_value_ids)
                    attr_names = ", ".join(self.attribute_value_ids.mapped("name")).strip()
                    variant_suffix = attr_names or ""

                    # Ensure template has name
                    # if not (template.name or "").strip():
                    #     template.sudo().write({"name": variant_suffix or "Product"})

                    new_variant = ProductProduct.create({
                        "product_tmpl_id": template.id,
                        "name": template.name,
                        **({"uom_id": self.product_uom_id.id} if self.product_uom_id else {}),
                    })

                    # Link PTAVs
                    if ptav_ids:
                        new_variant.write({
                            "product_template_attribute_value_ids": [(4, pid) for pid in ptav_ids]
                        })

                    # Fix name directly (no name_get in Odoo 18)
                    # display_name = variant_suffix or template.name or "Product"
                    # new_variant.sudo().write({"name": display_name})

                    variants = new_variant
                else:
                    raise UserError(_("No matching variant found and variant creation is disabled."))

        # 3) Fallback if still no variants
        if not variants:
            existing = ProductProduct.search([("product_tmpl_id", "=", self.product_tmpl_id.id)], limit=1)
            if existing:
                variants = existing
            else:
                if self.create_variant:
                    newv = ProductProduct.create({
                        "product_tmpl_id": self.product_tmpl_id.id,
                        "name": template.name,
                    })
                    variants = newv
                else:
                    raise UserError(_("No variants selected and no existing variants available."))

        variants = variants.sorted(key=lambda r: r.id)

        # Clean stored variant name
        for v in variants:
            tmpl = v.product_tmpl_id
            if not tmpl:
                continue
            stored_name = (v.name or "").strip()
            if stored_name and stored_name.startswith(tmpl.name):
                # print("======",stored_name,template.name,v.name,self.product_tmpl_id.name)
                # ssssssssssss
                suffix = stored_name[len(tmpl.name):].strip()
                if suffix.startswith("(") and suffix.endswith(")"):
                    suffix = suffix[1:-1].strip()
                v.sudo().write({"name": self.product_tmpl_id.name})
            elif not stored_name:
                vals = self._get_variant_attribute_values(v)
                if vals:
                    suffix = ", ".join(vals.mapped("name"))
                    v.sudo().write({"name":template.name})
                elif not tmpl.name:
                    tmpl.sudo().write({"name": "Product"})

        # Create / update BOM lines
        vals_common = {"product_qty": self.qty or 0.0}
        if self.product_uom_id:
            vals_common["product_uom_id"] = self.product_uom_id.id

        created_lines = self.env["mrp.bom.line"]
        if self.bom_line_id:
            first = variants[0]
            write_vals = dict(vals_common)
            write_vals.update({
                "product_id": first.id,
                "product_tmpl_id": first.product_tmpl_id.id if first.product_tmpl_id else False,
            })
            self.bom_line_id.write(write_vals)
            created_lines |= self.bom_line_id

            for v in variants[1:]:
                create_vals = {
                    "bom_id": self.bom_id.id if self.bom_id else self.bom_line_id.bom_id.id,
                    "product_id": v.id,
                    "product_tmpl_id": v.product_tmpl_id.id if v.product_tmpl_id else False,
                    **vals_common,
                }
                created_lines |= self.env["mrp.bom.line"].create(create_vals)
        else:
            if not self.bom_id:
                raise UserError(_("No BOM specified to create BOM lines under."))
            for v in variants:
                create_vals = {
                    "bom_id": self.bom_id.id,
                    "product_id": v.id,
                    "product_tmpl_id": v.product_tmpl_id.id if v.product_tmpl_id else False,
                    **vals_common,
                }
                created_lines |= self.env["mrp.bom.line"].create(create_vals)

        # ✅ Refresh BOM form so names display correctly
        if self.bom_id and self.bom_id.exists():
            return {
                "type": "ir.actions.act_window",
                "res_model": "mrp.bom",
                "res_id": self.bom_id.id,
                "view_mode": "form",
                "target": "current",
            }
        return {"type": "ir.actions.client", "tag": "reload"}


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def action_open_select_template_wizard(self):
        self.ensure_one()
        return {
            "name": _("Select Product Template"),
            "type": "ir.actions.act_window",
            "res_model": "select.product.template.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_bom_id": self.id,
                # "default_product_tmpl_id": self.product_tmpl_id.id if self.product_tmpl_id else False,
            },
        }


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product Template",
        ondelete="set null",
        help="Product template associated with this BOM line (optional)."
    )

    def action_open_select_template_wizard(self):
        self.ensure_one()
        return {
            "name": _("Select Product Template"),
            "type": "ir.actions.act_window",
            "res_model": "select.product.template.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_bom_line_id": self.id,
                "default_bom_id": self.bom_id.id,
                "default_qty": self.product_qty or 1.0,
            },
        }
