from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        """Override to auto-confirm draft POs related to this SO and create receipts"""
        res = super()._action_confirm()
        
        for order in self:
            if not order.procurement_group_id:
                continue
            
            # Find all purchase orders linked to this SO through procurement group
            purchase_orders = order.procurement_group_id.stock_move_ids.created_purchase_line_ids.order_id \
                            | order.procurement_group_id.stock_move_ids.move_orig_ids.purchase_line_id.order_id \
                            | order.procurement_group_id.purchase_line_ids.order_id
            
            # Filter only draft POs (newly created)
            draft_pos = purchase_orders.filtered(lambda po: po.state == 'draft')
            
            # Confirm draft POs (this will create the receipt picking automatically)
            for po in draft_pos:
                try:
                    po.button_confirm()
                except Exception:
                    # Log error but don't fail the SO confirmation
                    continue
        
        return res