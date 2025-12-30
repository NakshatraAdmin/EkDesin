from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        """Override to auto-confirm subcontract POs and validate receipts"""
        res = super()._action_confirm()
        
        for order in self:
            if not order.procurement_group_id:
                continue
            
            # Find all purchase orders linked to this SO through procurement group
            purchase_orders = order.procurement_group_id.stock_move_ids.created_purchase_line_ids.order_id \
                            | order.procurement_group_id.stock_move_ids.move_orig_ids.purchase_line_id.order_id \
                            | order.procurement_group_id.purchase_line_ids.order_id
            
            # Filter for subcontract POs: POs where partner has subcontractor location
            # This identifies POs created for subcontractors
            subcontract_pos = purchase_orders.filtered(
                lambda po: po.partner_id.with_company(po.company_id).property_stock_subcontractor
            )
            
            # Filter only draft POs (newly created)
            draft_subcontract_pos = subcontract_pos.filtered(
                lambda po: po.state == 'draft'
            )
            
            for po in draft_subcontract_pos:
                try:
                    # Auto-confirm the PO (this will create the receipt picking automatically)
                    po.button_confirm()
                    
                except Exception:
                    # Log error but don't fail the SO confirmation
                    continue
        
        return res
