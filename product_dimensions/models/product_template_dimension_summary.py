# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplateDimensionSummary(models.Model):
    _inherit = 'product.template'
    
    dimension_summary = fields.Char(
        string="Dimension Summary",
        compute="_compute_dimension_summary",
        help="Shows aggregated cubic feet and pieces from PO receipts minus BOM/MO consumption",
    )

    @api.depends('product_variant_ids')
    def _compute_dimension_summary(self):
        """Compute dimension summary: aggregate PO receipts, subtract BOM/MO consumption"""
        for product in self:
            # Get all product variants
            variants = product.product_variant_ids
            
            if not variants:
                product.dimension_summary = ""
                continue
            
            total_cubic_ft = 0.0
            total_qty = 0.0
            bom_cubic_ft = 0.0
            bom_qty = 0.0
            mo_cubic_ft = 0.0
            mo_qty = 0.0
            
            # PO Receipt Aggregation: Find all stock moves from PO receipts
            po_moves = self.env['stock.move'].search([
                ('purchase_line_id', '!=', False),
                ('product_id', 'in', variants.ids),
            ])
            
            for move in po_moves:
                # Always count quantity/pieces
                if move.product_uom_qty:
                    total_qty += move.product_uom_qty
                # Calculate cubic feet only if available
                if move.cubic_ft and move.product_uom_qty:
                    total_cubic_ft += move.secondary_product_uom_qty * move.product_uom_qty
            # BOM Subtraction: Find all BOM lines where this product is a component
            bom_lines = self.env['mrp.bom.line'].search([
                ('product_id', 'in', variants.ids),
            ])
            
            for bom_line in bom_lines:
                # Always count quantity/pieces
                bom_qty += bom_line.product_qty
                # Calculate cubic feet only if dimensions are available
                if bom_line.product_id.length and bom_line.product_id.width and bom_line.product_id.height:
                    line_cubic_ft = bom_line.product_id.length * bom_line.product_id.width * bom_line.product_id.height
                    bom_cubic_ft += line_cubic_ft * bom_line.product_qty
            
            # MO Subtraction: Find all MO raw material moves for this product
            mo_moves = self.env['stock.move'].search([
                ('raw_material_production_id', '!=', False),
                ('product_id', 'in', variants.ids),
            ])
            
            for move in mo_moves:
                # Always count quantity/pieces
                if move.product_uom_qty:
                    mo_qty += move.product_uom_qty
                # Calculate cubic feet only if available
                if move.cubic_ft and move.product_uom_qty:
                    mo_cubic_ft += move.secondary_product_uom_qty * move.product_uom_qty
            
            # Net Calculation
            net_cubic_ft = total_cubic_ft  - mo_cubic_ft
            net_qty = total_qty - bom_qty - mo_qty
            
            # Display Format - prioritize pieces, cubic feet is optional
            if net_qty != 0:
                if net_cubic_ft != 0:
                    product.dimension_summary = f"{net_cubic_ft:.2f} cft :- {net_qty:.0f} pcs"
                else:
                    # Show only pieces if cubic feet is not available
                    product.dimension_summary = f"0.00 cft :- {net_qty:.0f} pcs"
            else:
                product.dimension_summary = ""
