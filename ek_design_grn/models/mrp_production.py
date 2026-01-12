from odoo import api, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    @api.depends('origin', 'bom_id')
    def _compute_project_id(self):
        """Override to link project from PO when MO's origin matches receipt name"""
        # Preserve original behavior: if from_project_action context, don't set project_id
        if self.env.context.get('from_project_action'):
            # Keep original behavior - don't set project_id
            return
        
        for production in self:
            project_id = False
            
            # First, try to match receipt and get PO's project_id
            if production.origin:
                receipt = self.env['stock.picking'].search([
                    ('name', '=', production.origin),
                    ('purchase_id', '!=', False)
                ], limit=1)
                
                if receipt and receipt.purchase_id and receipt.purchase_id.project_id:
                    # If receipt matches and PO has project, use PO's project
                    project_id = receipt.purchase_id.project_id.id
            
            # If no receipt match found, use original logic (from bom_id)
            if not project_id:
                project_id = production.bom_id.project_id.id if production.bom_id else False
            
            production.project_id = project_id
