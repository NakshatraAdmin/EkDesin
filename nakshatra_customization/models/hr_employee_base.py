from odoo import models


class HrEmployeeBase(models.AbstractModel):
    """
    Extends hr.employee.base to add context when creating employee-related contacts.
    """

    _inherit = "hr.employee.base"

    def _create_work_contacts(self):
        """
        Injects `is_employee=True` into context when creating work contacts.
        Ensures the contact type is set appropriately for employee partners.
        """
        self_with_context = self.with_context(is_employee=True)
        return super(HrEmployeeBase, self_with_context)._create_work_contacts()
