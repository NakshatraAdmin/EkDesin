from odoo import fields, models, api


class ResPartner(models.Model):
    """
    Extends the res.partner model to manage custom contact types (customer/vendor/employee),
    generate structured sequence codes for contacts, and customize contact creation logic
    based on context.
    """

    _inherit = "res.partner"

    contact_type = fields.Selection(
        selection=[
            ("customer", "Customer"),
            ("vendor", "Vendor"),
            ("employee", "Employee"),
        ],
        string="Contact Type Hide",
    )
    contact_type_show = fields.Selection(
        [
            ("customer", "Customer"),
            ("vendor", "Vendor"),
        ],
        string="Contact Type",
    )
    cust_1 = fields.Char()
    cust_2 = fields.Char()
    cust_3 = fields.Char()
    ven_1 = fields.Char()
    ven_2 = fields.Char()
    ven_3 = fields.Char()
    emp_1 = fields.Char()
    emp_2 = fields.Char()
    emp_3 = fields.Char()

    sequence_code = fields.Char(string="Sequence", readonly=True, copy=False)
    _sql_constraints = [
        ("code_unique", "UNIQUE(sequence_code)", "Code name must be unique")
    ]

    set_contact_type_from_context = fields.Boolean(
        compute="_compute_set_contact_type_from_context",
    )
    is_employee = fields.Boolean(
        compute="_compute_is_employee",
    )

    def _compute_is_employee(self):
        """
        Computes whether the current partner is linked to an employee record.
        Sets `is_employee` to True if `employee_ids` exists.
        """
        for partner in self:
            partner.is_employee = bool(partner.employee_ids)

    def _compute_set_contact_type_from_context(self):
        """
        Determines whether the contact type should be preset from the context,
        typically set when creating from specific entry points (e.g., menu items).
        """
        for rec in self:
            rec.set_contact_type_from_context = self.env.context.get(
                "set_contact_type_from_context", False
            )

    @api.model
    def default_get(self, fields):
        """
        Sets default values for `contact_type` and `contact_type_show` based on
        the context provided during record creation.
        Supports 'customer', 'supplier', and 'is_employee' creation modes.
        """
        res = super().default_get(fields)
        search_mode = self.env.context.get("res_partner_search_mode")

        if search_mode == "customer":
            res["contact_type_show"] = "customer"
            res["contact_type"] = "customer"
            res["set_contact_type_from_context"] = True
        elif search_mode == "supplier":
            res["contact_type_show"] = "vendor"
            res["contact_type"] = "vendor"
            res["set_contact_type_from_context"] = True
        elif self.env.context.get("is_employee"):
            res["contact_type"] = "employee"
            res["set_contact_type_from_context"] = True
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sets contact_type from contact_type_show or parent.
        Uses simplified ir.sequence by contact_type for both parent and child contacts.
        """
        type_to_sequence = {
            "customer": "res.partner.customer",
            "vendor": "res.partner.vendor",
            "employee": "res.partner.employee",
        }

        for vals in vals_list:
            # Use contact_type_show if not set directly
            if not vals.get("contact_type") and vals.get("contact_type_show"):
                vals["contact_type"] = vals["contact_type_show"]

            # Inherit from parent if child
            parent_id = vals.get("parent_id")
            if parent_id and not vals.get("contact_type"):
                parent = self.browse(parent_id)
                vals["contact_type"] = parent.contact_type

        partners = super().create(vals_list)

        for partner, vals in zip(partners, vals_list):
            contact_type = vals.get("contact_type", partner.contact_type)
            parent_id = vals.get(
                "parent_id", partner.parent_id.id if partner.parent_id else False
            )

            if not contact_type:
                continue  # Skip if still missing

            sequence_code = type_to_sequence.get(contact_type)
            if sequence_code:
                partner.sequence_code = self.env["ir.sequence"].next_by_code(
                    sequence_code
                )

        return partners
