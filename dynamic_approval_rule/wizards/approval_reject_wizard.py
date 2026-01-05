from odoo import models, fields


class ApprovalRejectWizard(models.TransientModel):
    _name = "approval.reject.wizard"
    _description = "Approval Reject Wizard"

    request_id = fields.Many2one("approval.request", required=True, readonly=True)
    rejection_reason = fields.Text(string="Reason", required=True)

    def confirm_reject(self):
        self.request_id.write(
            {
                "rejection_reason": self.rejection_reason,
            }
        )
        self.request_id.check_for_approval("rejected")
        self.request_id.action_reject()
