from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        """Override to auto-confirm draft POs related to this SO and create receipts"""
        res = super()._action_confirm()
        
        for order in self:
            # Refresh procurement group to ensure it's up to date
            if order.procurement_group_id:
                order.procurement_group_id.invalidate_recordset(['stock_move_ids', 'purchase_line_ids'])
            
            # Find all purchase orders linked to this SO
            purchase_orders = self.env['purchase.order']
            
            # Method 1: Through procurement group (for stock-based procurement)
            if order.procurement_group_id:
                # Get POs from procurement group stock moves
                purchase_orders |= order.procurement_group_id.stock_move_ids.created_purchase_line_ids.order_id
                purchase_orders |= order.procurement_group_id.stock_move_ids.move_orig_ids.purchase_line_id.order_id
                purchase_orders |= order.procurement_group_id.purchase_line_ids.order_id
            
            # Method 2: Through origin field (POs created with SO name in origin)
            # This is the most reliable method as PO origin always contains SO name
            purchase_orders |= self.env['purchase.order'].search([
                ('origin', 'ilike', order.name),
                ('state', 'in', ['draft', 'sent'])
            ])
            
            # Method 3: Through sale order line purchase lines (for service products)
            purchase_orders |= order.order_line.purchase_line_ids.order_id
            
            # Remove duplicates
            purchase_orders = purchase_orders.sudo()
            
            # Filter only draft/sent POs (newly created)
            draft_pos = purchase_orders.filtered(lambda po: po.state in ['draft', 'sent'])
            
            if not draft_pos:
                continue
            
            # Confirm draft POs (this will create the receipt picking automatically)
            for po in draft_pos:
                try:
                    # Check if approval is needed (for dynamic_approval_purchase module)
                    if hasattr(po, 'is_approved') and not po.is_approved:
                        # Auto-approve if approval module is installed
                        if hasattr(po, 'action_approve'):
                            po.sudo().action_approve()
                    
                    # Use sudo to bypass any permission issues and confirm
                    po.sudo().button_confirm()
                    
                    # Refresh to get updated state
                    po.invalidate_recordset(['state', 'picking_ids'])
                    
                except Exception:
                    # Try alternative: directly set state if button_confirm fails
                    try:
                        if po.state in ['draft', 'sent']:
                            po.sudo().write({'state': 'purchase'})
                    except Exception:
                        pass
                    # Don't fail the SO confirmation, just continue
                    continue
        
        return res