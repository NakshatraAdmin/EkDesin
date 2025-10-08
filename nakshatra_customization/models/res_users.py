from odoo import api, models


class ResUsers(models.Model):
    """
    Extends user creation to ensure related partner is treated as an employee.
    """

    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Overrides the user creation to add `is_employee=True` to context,
        ensuring any linked partner is created with contact_type='employee'.
        """
        self_with_context = self.with_context(is_employee=True)
        return super(ResUsers, self_with_context).create(vals_list)
