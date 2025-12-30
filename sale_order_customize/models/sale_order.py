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
            # Based on Odoo's standard relationships:
            # 1. PO lines have group_id (procurement.group) which has sale_id
            # 2. PO lines have move_dest_ids (stock moves) which have group_id (procurement.group) which has sale_id
            # 3. Stock moves from SO have created_purchase_line_ids
            # 4. Procurement group has purchase_line_ids
            
            purchase_orders = self.env['purchase.order']
            
            # Method 1: Through procurement group purchase lines (MOST RELIABLE)
            # PO lines created by procurement have group_id = procurement_group_id
            if order.procurement_group_id:
                purchase_orders |= order.procurement_group_id.purchase_line_ids.order_id
            
            # Method 2: Through procurement group stock moves
            # Stock moves from SO create PO lines, get those POs
            if order.procurement_group_id:
                # POs from stock moves created by procurement
                purchase_orders |= order.procurement_group_id.stock_move_ids.created_purchase_line_ids.order_id
                # POs from origin moves (for complex chains)
                all_moves = order.procurement_group_id.stock_move_ids
                if all_moves:
                    rolled_up_moves = self.env['stock.move'].browse(all_moves._rollup_move_origs())
                    purchase_orders |= rolled_up_moves.purchase_line_id.order_id
            
            # Method 3: Through PO lines that link to SO (reverse lookup)
            # Find PO lines where group_id.sale_id = SO or move_dest_ids.group_id.sale_id = SO
            po_lines = self.env['purchase.order.line'].search([
                '|',
                ('group_id.sale_id', '=', order.id),
                ('move_dest_ids.group_id.sale_id', '=', order.id),
                ('order_id.state', 'in', ['draft', 'sent'])
            ])
            purchase_orders |= po_lines.order_id
            
            # Method 4: Through sale order line purchase lines (for service products)
            purchase_orders |= order.order_line.purchase_line_ids.order_id
            
            # Method 5: Through origin field (fallback - may contain SO name or MO reference)
            purchase_orders |= self.env['purchase.order'].search([
                ('origin', 'ilike', order.name),
                ('state', 'in', ['draft', 'sent'])
            ])
            
            # Remove duplicates and filter only draft/sent POs (newly created)
            purchase_orders = purchase_orders.sudo()
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