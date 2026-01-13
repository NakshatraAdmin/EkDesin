# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.model
    def default_get(self, fields_list):
        """Auto-generate lot_name for Raw Material products when opening popup in receipt operations"""
        res = super(StockMoveLine, self).default_get(fields_list)
        
        # Only for incoming pickings (receipts) and if lot_name is not already set
        if 'lot_name' in fields_list and not res.get('lot_name'):
            move_id = res.get('move_id') or self.env.context.get('default_move_id') or self.env.context.get('active_id')
            product_id = res.get('product_id') or self.env.context.get('default_product_id')
            
            if move_id and product_id:
                try:
                    move = self.env['stock.move'].browse(move_id) if isinstance(move_id, int) else move_id
                    product = self.env['product.product'].browse(product_id) if isinstance(product_id, int) else product_id
                    
                    # Check if it's an incoming picking (receipt) and product has tracking
                    if (move.exists() and move.picking_id and 
                        move.picking_id.picking_type_id.code == 'incoming' and 
                        product.exists() and product.tracking in ('lot', 'serial')):
                        
                        # Check if product category is Raw Material
                        category_type = self.env['stock.lot']._get_category_type_from_product(product)
                        if category_type == 'rm':
                            # Auto-generate lot number - this will appear in the popup when it opens
                            lot_number = self.env['stock.lot']._generate_lot_serial_number(product)
                            res['lot_name'] = lot_number
                except Exception:
                    # If any error, continue without auto-generation
                    pass
        
        return res

    @api.model
    def create(self, vals_list):
        """Auto-generate lot_name when creating move lines for Raw Material products in receipts"""
        # Convert single dict to list for consistency
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            # Auto-generate lot_name for Raw Material products in incoming pickings
            if 'lot_name' not in vals or not vals.get('lot_name'):
                move_id = vals.get('move_id')
                product_id = vals.get('product_id')
                
                if move_id and product_id:
                    try:
                        move = self.env['stock.move'].browse(move_id)
                        product = self.env['product.product'].browse(product_id)
                        
                        # Check if it's an incoming picking (receipt) and product has tracking
                        if (move.exists() and move.picking_id and 
                            move.picking_id.picking_type_id.code == 'incoming' and 
                            product.exists() and product.tracking in ('lot', 'serial')):
                            
                            # Check if product category is Raw Material
                            category_type = self.env['stock.lot']._get_category_type_from_product(product)
                            if category_type == 'rm':
                                # Auto-generate lot number
                                lot_number = self.env['stock.lot']._generate_lot_serial_number(product)
                                vals['lot_name'] = lot_number
                    except Exception:
                        # If any error, continue without auto-generation
                        pass
        
        return super(StockMoveLine, self).create(vals_list)
