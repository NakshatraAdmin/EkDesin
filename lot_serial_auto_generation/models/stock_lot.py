# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re


class StockLot(models.Model):
    _inherit = 'stock.lot'

    name = fields.Char(
        'Lot/Serial Number',
        required=True,
        help="Unique Lot/Serial Number - Auto-generated based on product category and financial year",
        index='trigram',
        default=''  # Override default sequence - let our create method auto-generate
    )

    @api.model
    def _get_indian_financial_year(self, date=None):
        """Calculate Indian Financial Year (April 1 - March 31)
        
        Args:
            date: datetime or date object. If None, uses today.
        
        Returns:
            tuple: (start_year, end_year) e.g., (2025, 2026) for FY25-26
        """
        if date is None:
            date = fields.Date.today()
        elif isinstance(date, datetime):
            date = date.date()
        
        year = date.year
        month = date.month
        
        # Indian FY starts April 1
        if month >= 4:
            # April to December: FY starts this year
            start_year = year
            end_year = year + 1
        else:
            # January to March: FY started last year
            start_year = year - 1
            end_year = year
        
        return (start_year, end_year)

    @api.model
    def _get_fy_string(self, date=None):
        """Get Financial Year string in format FY25-26
        
        Args:
            date: datetime or date object. If None, uses today.
        
        Returns:
            str: Financial year string like 'FY25-26'
        """
        start_year, end_year = self._get_indian_financial_year(date)
        # Get last 2 digits
        start_yy = str(start_year)[-2:]
        end_yy = str(end_year)[-2:]
        return f"FY{start_yy}-{end_yy}"

    @api.model
    def _get_category_type_from_product(self, product):
        """Determine category type (rm/sfg/fg) from product's category name
        
        Args:
            product: product.product record
        
        Returns:
            str: 'rm', 'sfg', or 'fg' (defaults to 'rm')
        """
        if not product or not product.categ_id:
            return 'rm'  # Default to Raw Material
        
        category_name = product.categ_id.name.upper()
        complete_name = product.categ_id.complete_name.upper() if product.categ_id.complete_name else ''
        
        # IMPORTANT: Check SFG before FG to avoid false matches
        # (since "SFG" contains "FG", we need to check SFG first)
        
        # Check for Semi-Finished Goods (SFG) - MUST check before FG
        if 'SFG' in category_name or 'SFG' in complete_name or 'SEMI' in category_name or 'SEMI' in complete_name:
            return 'sfg'
        
        # Check for Finished Goods (FG) - Check after SFG
        if 'FG' in category_name or 'FG' in complete_name or 'FINISHED' in category_name or 'FINISHED' in complete_name:
            return 'fg'
        
        # Check for Raw Material (RM)
        if 'RAW' in category_name or 'RAW' in complete_name or 'RM' in category_name or 'RM' in complete_name:
            return 'rm'
        
        # Default to Raw Material if no match
        return 'rm'

    @api.model
    def _get_category_identifier(self, category_type):
        """Get category identifier based on product type
        
        Args:
            category_type: 'rm', 'sfg', or 'fg'
        
        Returns:
            str: Category identifier like 'LOT-RM', 'LOT-SFG', 'SR-FG'
        """
        mapping = {
            'rm': 'LOT-RM',
            'sfg': 'LOT-SFG',
            'fg': 'SR-FG'
        }
        return mapping.get(category_type, 'LOT-RM')

    @api.model
    def _generate_lot_serial_number(self, product, date=None):
        """Generate lot/serial number based on requirements
        
        Format: ED/FY25-26/LOT-RM00000001
        
        Args:
            product: product.product record
            date: datetime or date object. If None, uses today.
        
        Returns:
            str: Generated lot/serial number
        """
        # Determine category type from product's existing category
        category_type = self._get_category_type_from_product(product)
        
        # Get financial year
        fy_string = self._get_fy_string(date)
        
        # Get category identifier
        category_identifier = self._get_category_identifier(category_type)
        
        # Build prefix for pattern matching
        prefix = f'ED/{fy_string}/{category_identifier}'
        
        # Use database query with proper locking to get max sequence
        # This ensures thread-safety and prevents duplicates
        # Use FOR UPDATE SKIP LOCKED to handle concurrent requests
        self.env.cr.execute("""
            SELECT name FROM stock_lot 
            WHERE name LIKE %s 
            ORDER BY name DESC 
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (f'{prefix}%',))
        
        result = self.env.cr.fetchone()
        max_seq = 0
        
        if result and result[0]:
            lot_name = result[0]
            # Extract sequence number using regex
            pattern = rf'^{re.escape(prefix)}(\d{{8}})$'
            match = re.match(pattern, lot_name)
            if match:
                max_seq = int(match.group(1))
        
        # Calculate next sequence (reset to 1 if new FY)
        next_seq = max_seq + 1
        
        # Format: 8-digit zero-padded
        seq_str = str(next_seq).zfill(8)
        
        # Build final number
        lot_number = f"{prefix}{seq_str}"
        
        # Double-check uniqueness (additional safety)
        existing = self.search([('name', '=', lot_number)], limit=1)
        if existing:
            # If somehow duplicate exists, increment and try again
            next_seq += 1
            seq_str = str(next_seq).zfill(8)
            lot_number = f"{prefix}{seq_str}"
        
        return lot_number

    @api.model
    def create(self, vals_list):
        """Override create to auto-generate lot/serial numbers
        
        Triggers:
        - GRN (Raw Materials): When Purchase Order creates receipt → stock.picking validated → lot created
        - SFG (Semi-Finished Goods): When Manufacturing Order confirmed → lot_producing_id created
        - FG (Finished Goods): When Manufacturing Order confirmed → lot_producing_id created
        """
        # Convert single dict to list for consistency
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            # Auto-generate if name is not provided, empty, or is from default sequence (not our format)
            should_auto_generate = False
            
            if 'product_id' in vals:
                product = self.env['product.product'].browse(vals['product_id'])
                
                # Only generate if product has tracking enabled
                if product.tracking in ('lot', 'serial'):
                    # Check if name is provided and matches our format
                    provided_name = vals.get('name', '').strip() if vals.get('name') else ''
                    
                    # If no name or empty, auto-generate
                    if not provided_name:
                        should_auto_generate = True
                    else:
                        # If name is provided but doesn't match our format, replace it with auto-generated
                        pattern = r'^ED/FY\d{2}-\d{2}/(LOT-RM|LOT-SFG|SR-FG)\d{8}$'
                        if not re.match(pattern, provided_name):
                            # This is likely from default sequence - replace with our format
                            should_auto_generate = True
                    
                    if should_auto_generate:
                        # Get creation date from context or current datetime
                        create_date = vals.get('create_date')
                        if not create_date:
                            create_date = self.env.context.get('default_create_date') or fields.Datetime.now()
                        # Generate the number based on requirements
                        vals['name'] = self._generate_lot_serial_number(product, create_date)
            
            # Validate format if name is manually provided (as per requirement: reject manual overrides)
            if 'name' in vals and vals.get('name'):
                name = vals['name']
                # Check if it matches the expected format exactly
                pattern = r'^ED/FY\d{2}-\d{2}/(LOT-RM|LOT-SFG|SR-FG)\d{8}$'
                if not re.match(pattern, name):
                    # Reject manual overrides that don't match format
                    raise ValidationError(
                        _('Manual override rejected. Invalid lot/serial number format.\n'
                          'Expected format: ED/FY25-26/LOT-RM00000001\n'
                          'Lot/Serial numbers are automatically generated based on product category and financial year.')
                    )
        
        return super(StockLot, self).create(vals_list)
